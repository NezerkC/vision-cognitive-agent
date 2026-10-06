export type PermissionLevel = 'read_only' | 'ask' | 'auto';

/**
 * What the chat does with a tool call the model requested:
 * - run: call it directly.
 * - ask: show the in-app approval prompt first.
 * - native_confirm: call it; the Rust command shows its own native confirmation that the webview cannot skip.
 * - deny: refuse without calling it.
 */
export type ToolDecision = 'run' | 'ask' | 'native_confirm' | 'deny';

// Reads go through approval too: a prompt-injected model could read .env or keys and send them out through
// web search. Only the explicitly autonomous level skips the prompt, and only inside the open workspace.
export function decideToolAccess(toolName: string, level: PermissionLevel): ToolDecision {
  switch (toolName) {
    case 'web_search':
      return 'run';
    case 'read_file':
      return level === 'auto' ? 'run' : 'ask';
    case 'write_file':
      if (level === 'read_only') return 'deny';
      return level === 'auto' ? 'run' : 'ask';
    case 'execute_powershell':
      return level === 'read_only' ? 'deny' : 'native_confirm';
    default:
      return 'deny';
  }
}
