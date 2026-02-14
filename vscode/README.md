# Comp Language Support for VS Code

This extension provides syntax highlighting and basic language support for the Comp programming language.

## Installation

To install this extension locally:

1. Open VS Code
2. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
3. Type "Install from VSIX"
4. Or alternatively, use the terminal in the `vscode` directory:

```bash
code --install-extension comp-language-support-0.1.0.vsix
```

## Development

To package this extension:

```bash
npm install -g vsce
vsce package
```

This will create a `.vsix` file that can be installed in VS Code.