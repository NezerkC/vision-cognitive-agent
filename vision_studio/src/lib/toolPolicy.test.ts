import { describe, expect, it } from 'vitest';
import { decideToolAccess } from './toolPolicy';

describe('decideToolAccess', () => {
  it('asks before reading a file unless the agent is fully autonomous', () => {
    expect(decideToolAccess('read_file', 'read_only')).toBe('ask');
    expect(decideToolAccess('read_file', 'ask')).toBe('ask');
    expect(decideToolAccess('read_file', 'auto')).toBe('run');
  });

  it('blocks writes in read-only mode and asks before them in ask mode', () => {
    expect(decideToolAccess('write_file', 'read_only')).toBe('deny');
    expect(decideToolAccess('write_file', 'ask')).toBe('ask');
    expect(decideToolAccess('write_file', 'auto')).toBe('run');
  });

  it('leaves PowerShell confirmation to the native dialog in Rust', () => {
    expect(decideToolAccess('execute_powershell', 'read_only')).toBe('deny');
    expect(decideToolAccess('execute_powershell', 'ask')).toBe('native_confirm');
    expect(decideToolAccess('execute_powershell', 'auto')).toBe('native_confirm');
  });

  it('runs web search in every mode', () => {
    expect(decideToolAccess('web_search', 'read_only')).toBe('run');
    expect(decideToolAccess('web_search', 'auto')).toBe('run');
  });

  it('denies tools it does not know', () => {
    expect(decideToolAccess('delete_everything', 'auto')).toBe('deny');
  });
});
