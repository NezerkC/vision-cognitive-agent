/** Separator before the JSON error the gateway appends when a notebook chat stream fails after it started. */
export const CHAT_STREAM_ERROR_MARKER = '\u001e';

const STREAM_FAILED = 'El cuaderno no pudo completar la respuesta.';

/** The message of a gateway error body ({status: 'error', message}), or the fallback. */
export function apiErrorMessage(body: unknown, fallback: string): string {
  const message = (body as { message?: unknown } | null)?.message;
  return typeof message === 'string' && message ? message : fallback;
}

/** Split streamed notebook chat text into the answer and the error event that ends a failed stream. */
export function splitChatStream(text: string): { answer: string; error: string | null } {
  const at = text.indexOf(CHAT_STREAM_ERROR_MARKER);
  if (at < 0) return { answer: text, error: null };
  let body: unknown = null;
  try {
    body = JSON.parse(text.slice(at + CHAT_STREAM_ERROR_MARKER.length));
  } catch {
    body = null;
  }
  return { answer: text.slice(0, at).trimEnd(), error: apiErrorMessage(body, STREAM_FAILED) };
}
