<p align="center">
  <img src="images/Logo.png" width="300" />
</p>

CodeFlowMap reads any codebase like a Senior Staff Engineer and maps it into detailed **C4-style Mermaid diagrams** — at both component and class level. It is available in two flavours depending on your workflow.

---

## Implementations

### VS Code Custom Agent

A VS Code Custom Agent that integrates directly into your editor. Point it at your workspace and get architecture diagrams without leaving the IDE.

→ [Read the VS Code README](./vscode/README.md)

---

### DeepAgent CLI Tool

A CLI deep-agent that runs an autonomous multi-step analysis loop using [LangChain DeepAgents](https://docs.langchain.com/oss/python/deepagents/). Point it at any local repo, approve the plan, and receive a fully generated `codeflowmap.md` file.

→ [Read the DeepAgent README](./deepagent/README.md)

---

## What both produce

- **Component Diagram** (C4 Level 3) — major runtime components, external systems, and labelled communication edges
- **Class Diagram** (C4 Level 4) — classes, interfaces, inheritance, composition, and design patterns

Both render as Mermaid diagrams inside Markdown, viewable directly in GitHub or any Mermaid-compatible renderer.
