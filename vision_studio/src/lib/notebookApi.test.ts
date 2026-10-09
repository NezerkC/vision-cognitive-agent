import { describe, expect, it } from 'vitest';
import { apiErrorMessage, CHAT_STREAM_ERROR_MARKER, splitChatStream } from './notebookApi';

describe('apiErrorMessage', () => {
  it('uses the message of a gateway error body', () => {
    expect(apiErrorMessage({ status: 'error', message: 'El cuaderno no tiene fuentes indexadas.' }, 'Error 409'))
      .toBe('El cuaderno no tiene fuentes indexadas.');
  });

  it('falls back when the body carries no message', () => {
    expect(apiErrorMessage(null, 'Error 500')).toBe('Error 500');
    expect(apiErrorMessage({ detail: 'Not Found' }, 'Error 404')).toBe('Error 404');
    expect(apiErrorMessage('texto plano', 'Error 502')).toBe('Error 502');
  });
});

describe('splitChatStream', () => {
  it('keeps the whole text as the answer when the stream did not fail', () => {
    expect(splitChatStream('Respuesta [Fuente: doc.txt]')).toEqual({ answer: 'Respuesta [Fuente: doc.txt]', error: null });
  });

  it('separates the error event that ends a failed stream', () => {
    const text = `[🌐 Buscando en la web...]\n\n${CHAT_STREAM_ERROR_MARKER}{"status": "error", "message": "El modelo de lenguaje no respondió"}\n`;
    expect(splitChatStream(text)).toEqual({
      answer: '[🌐 Buscando en la web...]',
      error: 'El modelo de lenguaje no respondió',
    });
  });

  it('still reports a failure when the error event is not valid JSON', () => {
    expect(splitChatStream(`hola${CHAT_STREAM_ERROR_MARKER}{"stat`)).toEqual({
      answer: 'hola',
      error: 'El cuaderno no pudo completar la respuesta.',
    });
  });
});
