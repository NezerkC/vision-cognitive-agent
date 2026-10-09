"""
ComfyUI adapter for the IImageGenerator port (local-first imagination and dreams).

Flow: POST /prompt queues the workflow with a client_id; GET /history/{prompt_id} is polled until the run appears;
GET /view downloads the saved image.
- Unreachable, refused or unanswered connections raise ImageGeneratorUnavailableError.
- A rejected workflow, a node execution error, a run that does not finish within timeout_seconds, or a run without
  an image raise ImageGenerationFailedError.

Workflow: an API-format graph (ComfyUI "Save (API Format)"). Values are injected by node role, found through the
links of the KSampler, so node ids may differ:
- checkpoint: the CheckpointLoaderSimple feeding KSampler.model (ckpt_name)
- positive and negative prompt: the CLIPTextEncode nodes feeding KSampler.positive and KSampler.negative (text)
- size: the EmptyLatentImage feeding KSampler.latent_image (width, height)
- steps and seed: KSampler inputs steps and seed (or noise_seed)
A random seed is used when ImageOptions.seed is None. Every value used goes into GeneratedImage.metadata.

Configuration: config/imaginacion.json, key "comfyui" (read by comfyui_from_config).
"""

import asyncio
import copy
import json
import mimetypes
import os
import secrets
import urllib.parse
import uuid
from typing import Any, NamedTuple

import aiohttp

from core.ports.image_generator import (
    GeneratedImage,
    ImageGenerationFailedError,
    ImageGeneratorUnavailableError,
    ImageOptions,
)

GENERATOR_ID = "comfyui"
DEFAULT_URL = "http://127.0.0.1:8188"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_WORKFLOW_RELPATH = os.path.join("config", "comfyui_txt2img.json")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_WORKFLOW = os.path.join(PROJECT_ROOT, DEFAULT_WORKFLOW_RELPATH)
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "imaginacion.json")


class _Roles(NamedTuple):
    sampler: str
    checkpoint: str
    positive: str
    negative: str
    latent: str


def load_workflow(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        workflow = json.load(f)
    if not isinstance(workflow, dict):
        raise ValueError(f"ComfyUI workflow {path} must be an API-format JSON object")
    return workflow


def _linked_node(workflow: dict[str, Any], inputs: dict[str, Any], name: str, class_type: str) -> str:
    link = inputs.get(name)
    if not (isinstance(link, list) and len(link) == 2 and str(link[0]) in workflow):
        raise ValueError(f"workflow KSampler input '{name}' must link to a node")
    node_id = str(link[0])
    if workflow[node_id].get("class_type") != class_type:
        raise ValueError(f"workflow KSampler input '{name}' must come from a {class_type} node")
    return node_id


def _require_literal(workflow: dict[str, Any], node_id: str, keys: list[str]) -> None:
    inputs = workflow[node_id]["inputs"]
    for key in keys:
        if key not in inputs:
            raise ValueError(f"workflow node {node_id} ({workflow[node_id]['class_type']}) has no '{key}' input")
        if isinstance(inputs[key], list):
            raise ValueError(f"workflow node {node_id} input '{key}' must be a literal value, not a link")


def _find_roles(workflow: dict[str, Any]) -> _Roles:
    samplers = [node_id for node_id, node in workflow.items() if node.get("class_type") == "KSampler"]
    if len(samplers) != 1:
        raise ValueError(f"workflow needs exactly one KSampler node, found {len(samplers)}")
    sampler = samplers[0]
    inputs = workflow[sampler]["inputs"]
    roles = _Roles(
        sampler=sampler,
        checkpoint=_linked_node(workflow, inputs, "model", "CheckpointLoaderSimple"),
        positive=_linked_node(workflow, inputs, "positive", "CLIPTextEncode"),
        negative=_linked_node(workflow, inputs, "negative", "CLIPTextEncode"),
        latent=_linked_node(workflow, inputs, "latent_image", "EmptyLatentImage"),
    )
    _require_literal(workflow, roles.sampler, ["steps"])
    if "seed" not in inputs and "noise_seed" not in inputs:
        raise ValueError("workflow KSampler needs a 'seed' or 'noise_seed' input")
    _require_literal(workflow, roles.checkpoint, ["ckpt_name"])
    _require_literal(workflow, roles.positive, ["text"])
    _require_literal(workflow, roles.negative, ["text"])
    _require_literal(workflow, roles.latent, ["width", "height"])
    return roles


def _inject(
    workflow: dict[str, Any],
    roles: _Roles,
    prompt: str,
    options: ImageOptions,
    seed: int,
    checkpoint: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = copy.deepcopy(workflow)
    sampler = graph[roles.sampler]["inputs"]
    positive = graph[roles.positive]["inputs"]
    negative = graph[roles.negative]["inputs"]
    latent = graph[roles.latent]["inputs"]
    loader = graph[roles.checkpoint]["inputs"]

    positive["text"] = prompt
    if options.negative_prompt is not None:
        negative["text"] = options.negative_prompt
    if options.width is not None:
        latent["width"] = options.width
    if options.height is not None:
        latent["height"] = options.height
    if options.steps is not None:
        sampler["steps"] = options.steps
    sampler["seed" if "seed" in sampler else "noise_seed"] = seed
    if checkpoint is not None:
        loader["ckpt_name"] = checkpoint

    used = {
        "checkpoint": loader["ckpt_name"],
        "width": latent["width"],
        "height": latent["height"],
        "steps": sampler["steps"],
        "seed": seed,
        "negative_prompt": negative["text"],
    }
    return graph, used


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _describe_rejection(data: Any, body: str) -> str:
    details = []
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            details.append(str(error["message"]))
        node_errors = data.get("node_errors")
        if isinstance(node_errors, dict):
            for node_id, info in node_errors.items():
                errors = info.get("errors", []) if isinstance(info, dict) else []
                for item in errors:
                    message = item.get("message", "error") if isinstance(item, dict) else "error"
                    details.append(f"node {node_id}: {message}")
    return "; ".join(details) or body[:200] or "no details"


def _execution_error(status: dict[str, Any]) -> str:
    for message in status.get("messages") or []:
        if isinstance(message, list) and len(message) == 2 and message[0] == "execution_error":
            detail = message[1] if isinstance(message[1], dict) else {}
            return str(detail.get("exception_message") or "unknown error")
    return "unknown error"


def _output_image(entry: dict[str, Any]) -> dict[str, Any]:
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    if status.get("status_str") == "error":
        raise ImageGenerationFailedError(GENERATOR_ID, f"ComfyUI execution failed: {_execution_error(status)}")
    outputs = entry.get("outputs") if isinstance(entry.get("outputs"), dict) else {}
    for output in outputs.values():
        images = output.get("images") if isinstance(output, dict) else None
        for image in images or []:
            if isinstance(image, dict) and image.get("filename") and image.get("type", "output") == "output":
                return image
    raise ImageGenerationFailedError(GENERATOR_ID, "no image was produced: the run finished without output images")


class ComfyUIImageGenerator:
    """IImageGenerator backed by a ComfyUI server. `workflow` is the API-format graph used as the template."""

    def __init__(
        self,
        workflow: dict[str, Any],
        base_url: str = DEFAULT_URL,
        checkpoint: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        request_timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 1.0,
    ):
        self._roles = _find_roles(workflow)
        self._workflow = copy.deepcopy(workflow)
        self._base_url = base_url.rstrip("/")
        self._checkpoint = checkpoint
        self._timeout_seconds = timeout_seconds
        self._poll_interval = poll_interval_seconds
        self._request_timeout = aiohttp.ClientTimeout(total=request_timeout_seconds)

    @property
    def generator_id(self) -> str:
        return GENERATOR_ID

    async def is_available(self) -> bool:
        try:
            async with aiohttp.ClientSession(timeout=self._request_timeout) as session:
                async with session.get(f"{self._base_url}/system_stats") as resp:
                    return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def generate(self, prompt: str, options: ImageOptions | None = None) -> GeneratedImage:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if options is None:
            options = ImageOptions()
        seed = options.seed if options.seed is not None else secrets.randbelow(2**32)
        graph, used = _inject(self._workflow, self._roles, prompt, options, seed, self._checkpoint)

        async with aiohttp.ClientSession(timeout=self._request_timeout) as session:
            prompt_id = await self._queue(session, graph)
            image = await self._wait_for_image(session, prompt_id)
            data, mime_type = await self._download(session, image)

        return GeneratedImage(
            data=data,
            mime_type=mime_type,
            generator_id=GENERATOR_ID,
            prompt=prompt,
            metadata={**used, "prompt_id": prompt_id},
        )

    async def _queue(self, session: aiohttp.ClientSession, graph: dict[str, Any]) -> str:
        try:
            async with session.post(
                f"{self._base_url}/prompt", json={"prompt": graph, "client_id": uuid.uuid4().hex}
            ) as resp:
                status = resp.status
                body = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as e:
            raise ImageGeneratorUnavailableError(
                GENERATOR_ID, f"ComfyUI at {self._base_url} is unreachable or not answering"
            ) from e

        data = _parse_json(body)
        rejected = status != 200 or (isinstance(data, dict) and bool(data.get("node_errors")))
        if rejected:
            reason = _describe_rejection(data, body)
            raise ImageGenerationFailedError(GENERATOR_ID, f"ComfyUI rejected the workflow (HTTP {status}): {reason}")
        prompt_id = data.get("prompt_id") if isinstance(data, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ImageGenerationFailedError(GENERATOR_ID, "ComfyUI did not return a prompt_id")
        return prompt_id

    async def _wait_for_image(self, session: aiohttp.ClientSession, prompt_id: str) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_seconds
        while True:
            entry = await self._history_entry(session, prompt_id)
            if entry is not None:
                return _output_image(entry)
            if loop.time() >= deadline:
                raise ImageGenerationFailedError(
                    GENERATOR_ID,
                    f"no image after {self._timeout_seconds:g} s (prompt {prompt_id} is still not finished)",
                )
            await asyncio.sleep(self._poll_interval)

    async def _history_entry(self, session: aiohttp.ClientSession, prompt_id: str) -> dict[str, Any] | None:
        url = f"{self._base_url}/history/{urllib.parse.quote(prompt_id, safe='')}"
        try:
            async with session.get(url) as resp:
                status = resp.status
                body = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as e:
            raise ImageGeneratorUnavailableError(
                GENERATOR_ID, f"lost ComfyUI at {self._base_url} while waiting for prompt {prompt_id}"
            ) from e
        if status != 200:
            raise ImageGenerationFailedError(GENERATOR_ID, f"history request failed (HTTP {status})")
        data = _parse_json(body)
        entry = data.get(prompt_id) if isinstance(data, dict) else None
        return entry if isinstance(entry, dict) else None

    async def _download(self, session: aiohttp.ClientSession, image: dict[str, Any]) -> tuple[bytes, str]:
        filename = str(image["filename"])
        params = {
            "filename": filename,
            "subfolder": str(image.get("subfolder", "")),
            "type": str(image.get("type", "output")),
        }
        try:
            async with session.get(f"{self._base_url}/view", params=params) as resp:
                status = resp.status
                content_type = resp.content_type
                data = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as e:
            raise ImageGeneratorUnavailableError(
                GENERATOR_ID, f"lost ComfyUI at {self._base_url} while downloading {filename}"
            ) from e
        if status != 200:
            raise ImageGenerationFailedError(GENERATOR_ID, f"download of {filename} failed (HTTP {status})")
        if not data:
            raise ImageGenerationFailedError(GENERATOR_ID, f"{filename} downloaded empty")
        mime_type = content_type if content_type.startswith("image/") else mimetypes.guess_type(filename)[0] or ""
        if not mime_type.startswith("image/"):
            raise ImageGenerationFailedError(GENERATOR_ID, f"unknown image type for {filename}")
        return data, mime_type


def comfyui_from_config(config_path: str = DEFAULT_CONFIG_PATH) -> ComfyUIImageGenerator:
    """Builds the adapter from the "comfyui" entry of config/imaginacion.json; missing keys keep the defaults."""
    settings: dict[str, Any] = {}
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            settings = json.load(f).get("comfyui") or {}
    workflow_path = os.path.join(PROJECT_ROOT, settings.get("workflow", DEFAULT_WORKFLOW_RELPATH))
    return ComfyUIImageGenerator(
        load_workflow(workflow_path),
        base_url=settings.get("url", DEFAULT_URL),
        checkpoint=settings.get("checkpoint"),
        timeout_seconds=float(settings.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
    )
