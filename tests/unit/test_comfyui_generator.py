"""
Unit tests for the ComfyUI image adapter. A fake ComfyUI HTTP server runs on loopback and serves the three
endpoints the adapter uses (POST /prompt, GET /history/{id}, GET /view); nothing reaches a real ComfyUI.
"""

import asyncio
import copy
import json
import socket
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from core.adapters.comfyui_image_generator import (
    DEFAULT_WORKFLOW,
    ComfyUIImageGenerator,
    comfyui_from_config,
    load_workflow,
)
from core.ports.image_generator import (
    IImageGenerator,
    ImageGenerationFailedError,
    ImageGeneratorUnavailableError,
    ImageOptions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_CONFIG = PROJECT_ROOT / "config" / "imaginacion.json"
PNG = b"\x89PNG\r\n\x1a\n" + b"image bytes from the fake ComfyUI"
PROMPT_ID = "5f3c2b1a-prompt"
WORKFLOW = load_workflow(DEFAULT_WORKFLOW)


class FakeComfyUI:
    """Behaviour is switched per test through the attributes; the defaults describe a healthy run."""

    def __init__(self):
        self.url = ""
        self.queued = []
        self.history_calls = 0
        self.views = []
        self.pending_history_polls = 0
        self.prompt_status = 200
        self.prompt_reply = {"prompt_id": PROMPT_ID, "number": 0, "node_errors": {}}
        self.prompt_delay = 0.0
        self.execution_status = "success"
        self.execution_messages = []
        self.images = [{"filename": "vision_os_00001_.png", "subfolder": "", "type": "output"}]
        self.view_status = 200
        self.view_body = PNG

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/prompt", self._prompt)
        app.router.add_get("/history/{prompt_id}", self._history)
        app.router.add_get("/view", self._view)
        app.router.add_get("/system_stats", self._system_stats)
        return app

    async def _prompt(self, request: web.Request) -> web.Response:
        self.queued.append(await request.json())
        if self.prompt_delay:
            await asyncio.sleep(self.prompt_delay)
        return web.json_response(self.prompt_reply, status=self.prompt_status)

    async def _history(self, request: web.Request) -> web.Response:
        self.history_calls += 1
        if self.history_calls <= self.pending_history_polls:
            return web.json_response({})
        outputs = {"9": {"images": self.images}} if self.execution_status == "success" else {}
        entry = {
            "prompt": [],
            "outputs": outputs,
            "status": {
                "status_str": self.execution_status,
                "completed": self.execution_status == "success",
                "messages": self.execution_messages,
            },
        }
        return web.json_response({request.match_info["prompt_id"]: entry})

    async def _view(self, request: web.Request) -> web.Response:
        self.views.append(dict(request.query))
        return web.Response(body=self.view_body, status=self.view_status, content_type="image/png")

    async def _system_stats(self, request: web.Request) -> web.Response:
        return web.json_response({"system": {"comfyui_version": "fake"}})


@pytest.fixture
async def comfy():
    fake = FakeComfyUI()
    server = TestServer(fake.app())
    await server.start_server()
    fake.url = str(server.make_url("")).rstrip("/")
    yield fake
    await server.close()


def unused_url() -> str:
    """A loopback address with nothing listening: connections are refused."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


def make_generator(url: str, workflow: dict | None = None, **settings) -> ComfyUIImageGenerator:
    defaults = {"poll_interval_seconds": 0.01, "timeout_seconds": 2.0, "request_timeout_seconds": 2.0}
    defaults.update(settings)
    return ComfyUIImageGenerator(
        workflow if workflow is not None else copy.deepcopy(WORKFLOW), base_url=url, **defaults
    )


def queued_prompt(fake: FakeComfyUI) -> dict:
    return fake.queued[-1]["prompt"]


def node_of_class(prompt: dict, class_type: str) -> dict:
    found = [node for node in prompt.values() if node["class_type"] == class_type]
    assert len(found) == 1, f"expected one {class_type} node"
    return found[0]


def linked_node(prompt: dict, node: dict, input_name: str) -> dict:
    node_id, _slot = node["inputs"][input_name]
    return prompt[node_id]


def renumber(workflow: dict, offset: int = 100) -> dict:
    """Same graph with every node id moved, so any id-based injection would break."""
    mapping = {old: str(int(old) + offset) for old in workflow}
    renumbered = {}
    for old, node in workflow.items():
        inputs = {
            key: [mapping[value[0]], value[1]] if isinstance(value, list) else value
            for key, value in node["inputs"].items()
        }
        renumbered[mapping[old]] = {**node, "inputs": inputs}
    return renumbered


def sampler_id(workflow: dict) -> str:
    return next(node_id for node_id, node in workflow.items() if node["class_type"] == "KSampler")


def test_the_shipped_workflow_is_a_connected_txt2img_graph():
    classes = {node["class_type"] for node in WORKFLOW.values()}
    assert {"KSampler", "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "VAEDecode"} <= classes
    assert "SaveImage" in classes
    for node in WORKFLOW.values():
        for value in node["inputs"].values():
            if isinstance(value, list):
                assert value[0] in WORKFLOW


def test_the_adapter_satisfies_the_port_and_names_itself_comfyui():
    generator = make_generator("http://127.0.0.1:1")
    assert isinstance(generator, IImageGenerator)
    assert generator.generator_id == "comfyui"


def test_a_workflow_without_a_sampler_is_rejected_when_the_adapter_is_built():
    workflow = copy.deepcopy(WORKFLOW)
    workflow.pop(sampler_id(workflow))
    with pytest.raises(ValueError, match="KSampler"):
        ComfyUIImageGenerator(workflow)


def test_a_workflow_without_a_steps_input_is_rejected_when_the_adapter_is_built():
    workflow = copy.deepcopy(WORKFLOW)
    del workflow[sampler_id(workflow)]["inputs"]["steps"]
    with pytest.raises(ValueError, match="steps"):
        ComfyUIImageGenerator(workflow)


async def test_generate_queues_the_prompt_polls_history_and_downloads_the_image(comfy):
    image = await make_generator(comfy.url).generate("un faro en la niebla")

    assert image.data == PNG
    assert image.mime_type == "image/png"
    assert image.generator_id == "comfyui"
    assert image.prompt == "un faro en la niebla"
    assert len(comfy.queued) == 1
    assert comfy.queued[0]["client_id"]
    assert comfy.history_calls >= 1
    assert comfy.views == [{"filename": "vision_os_00001_.png", "subfolder": "", "type": "output"}]
    assert image.metadata["prompt_id"] == PROMPT_ID
    assert image.metadata["checkpoint"] == "v1-5-pruned-emaonly.ckpt"
    assert image.metadata["steps"] == 20
    assert (image.metadata["width"], image.metadata["height"]) == (512, 512)
    assert image.metadata["negative_prompt"] == "bad quality, blurry, deformed"


async def test_history_is_polled_until_the_outputs_appear(comfy):
    comfy.pending_history_polls = 3

    image = await make_generator(comfy.url).generate("un faro")

    assert image.data == PNG
    assert comfy.history_calls == 4


async def test_options_and_checkpoint_are_injected_by_node_role(comfy):
    generator = make_generator(comfy.url, checkpoint="dreams.safetensors")
    options = ImageOptions(width=640, height=384, steps=30, seed=7, negative_prompt="blurry")

    image = await generator.generate("un faro", options)

    prompt = queued_prompt(comfy)
    sampler = node_of_class(prompt, "KSampler")
    assert sampler["inputs"]["steps"] == 30
    assert sampler["inputs"]["seed"] == 7
    assert linked_node(prompt, sampler, "positive")["inputs"]["text"] == "un faro"
    assert linked_node(prompt, sampler, "negative")["inputs"]["text"] == "blurry"
    latent = linked_node(prompt, sampler, "latent_image")["inputs"]
    assert (latent["width"], latent["height"]) == (640, 384)
    assert node_of_class(prompt, "CheckpointLoaderSimple")["inputs"]["ckpt_name"] == "dreams.safetensors"
    assert image.metadata["checkpoint"] == "dreams.safetensors"
    assert image.metadata["seed"] == 7
    assert image.metadata["steps"] == 30
    assert (image.metadata["width"], image.metadata["height"]) == (640, 384)
    assert image.metadata["negative_prompt"] == "blurry"


async def test_roles_are_found_through_links_so_node_ids_do_not_matter(comfy):
    workflow = renumber(copy.deepcopy(WORKFLOW))

    await make_generator(comfy.url, workflow=workflow).generate("un faro", ImageOptions(steps=12))

    prompt = queued_prompt(comfy)
    assert set(prompt) == set(workflow)
    sampler = node_of_class(prompt, "KSampler")
    assert sampler["inputs"]["steps"] == 12
    assert linked_node(prompt, sampler, "positive")["inputs"]["text"] == "un faro"


async def test_a_random_seed_is_used_and_recorded_when_none_is_given(comfy):
    image = await make_generator(comfy.url).generate("un faro")

    sent = node_of_class(queued_prompt(comfy), "KSampler")["inputs"]["seed"]
    assert isinstance(image.metadata["seed"], int)
    assert image.metadata["seed"] == sent
    assert sent >= 0


async def test_generate_does_not_change_the_workflow_it_was_given(comfy):
    workflow = copy.deepcopy(WORKFLOW)

    await make_generator(comfy.url, workflow=workflow).generate("un faro", ImageOptions(seed=1, steps=5))

    assert workflow == WORKFLOW


async def test_an_unreachable_comfyui_raises_unavailable_with_the_cause():
    with pytest.raises(ImageGeneratorUnavailableError) as raised:
        await make_generator(unused_url()).generate("un faro")

    assert raised.value.generator_id == "comfyui"
    assert raised.value.__cause__ is not None


async def test_a_queue_request_that_hangs_is_unavailable(comfy):
    comfy.prompt_delay = 2.0

    with pytest.raises(ImageGeneratorUnavailableError):
        await make_generator(comfy.url, request_timeout_seconds=0.2).generate("un faro")


async def test_is_available_is_false_when_comfyui_is_unreachable():
    assert await make_generator(unused_url()).is_available() is False


async def test_is_available_is_true_when_comfyui_answers(comfy):
    assert await make_generator(comfy.url).is_available() is True


async def test_a_rejected_workflow_is_a_failed_generation(comfy):
    comfy.prompt_status = 400
    comfy.prompt_reply = {
        "error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation"},
        "node_errors": {"6": {"errors": [{"message": "Required input is missing", "details": "clip"}]}},
    }

    with pytest.raises(ImageGenerationFailedError) as raised:
        await make_generator(comfy.url).generate("un faro")

    assert "Required input is missing" in raised.value.reason


async def test_a_node_execution_error_is_a_failed_generation(comfy):
    comfy.execution_status = "error"
    comfy.execution_messages = [
        ["execution_error", {"node_id": 3, "node_type": "KSampler", "exception_message": "CUDA out of memory"}]
    ]

    with pytest.raises(ImageGenerationFailedError) as raised:
        await make_generator(comfy.url).generate("un faro")

    assert "CUDA out of memory" in raised.value.reason


async def test_a_finished_run_without_images_is_a_failed_generation(comfy):
    comfy.images = []

    with pytest.raises(ImageGenerationFailedError) as raised:
        await make_generator(comfy.url).generate("un faro")

    assert "no image" in raised.value.reason.lower()


@pytest.mark.parametrize("view_status, view_body", [(200, b""), (500, PNG)])
async def test_a_failed_or_empty_download_is_a_failed_generation(comfy, view_status, view_body):
    comfy.view_status = view_status
    comfy.view_body = view_body

    with pytest.raises(ImageGenerationFailedError):
        await make_generator(comfy.url).generate("un faro")


async def test_a_run_that_never_finishes_fails_at_the_wait_timeout(comfy):
    comfy.pending_history_polls = 10**6

    with pytest.raises(ImageGenerationFailedError) as raised:
        await make_generator(comfy.url, timeout_seconds=0.2).generate("un faro")

    assert "0.2" in raised.value.reason


async def test_the_configuration_file_sets_url_checkpoint_and_workflow(comfy, tmp_path):
    workflow_path = tmp_path / "flow.json"
    workflow_path.write_text(json.dumps(WORKFLOW), encoding="utf-8")
    config_path = tmp_path / "imaginacion.json"
    config_path.write_text(
        json.dumps(
            {
                "comfyui": {
                    "url": comfy.url,
                    "workflow": str(workflow_path),
                    "checkpoint": "dreams.safetensors",
                    "timeout_seconds": 30,
                }
            }
        ),
        encoding="utf-8",
    )

    image = await comfyui_from_config(str(config_path)).generate("un faro")

    assert image.data == PNG
    assert node_of_class(queued_prompt(comfy), "CheckpointLoaderSimple")["inputs"]["ckpt_name"] == "dreams.safetensors"


def test_the_shipped_configuration_builds_a_generator_from_the_shipped_workflow():
    generator = comfyui_from_config(str(SHIPPED_CONFIG))

    assert generator.generator_id == "comfyui"


def test_a_missing_configuration_file_falls_back_to_the_shipped_defaults(tmp_path):
    generator = comfyui_from_config(str(tmp_path / "missing.json"))

    assert generator.generator_id == "comfyui"
