# ADR 0001 — Servidor MCP no SDK Python 2, revisão 2026-07-28

- Status: aceita
- Data: 2026-10-03

## Contexto

O servidor expunha `search_docs` e `ask_about_docs` com `FastMCP` (`mcp.server.fastmcp`) e o pin `mcp>=1.4.0`. O transporte já era Streamable HTTP. O README testava o handshake `initialize` com `protocolVersion: 2025-03-26` e o header `Mcp-Session-Id`.

A revisão vigente da especificação é **2026-07-28**, sucessora de 2025-11-25. Fontes: [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http), [post do protocolo](https://blog.modelcontextprotocol.io/posts/2026-07-28/).

| Tema | Até 2025-11-25 | 2026-07-28 |
| --- | --- | --- |
| Sessão | Handshake `initialize` + header `Mcp-Session-Id` | Sem sessão de protocolo. Cada request carrega versão e capacidades em `_meta`. Estado entre chamadas, se existir, é um handle explícito passado como argumento de tool. |
| Descoberta | `initialize` | RPC `server/discover`. O handshake antigo deixa de existir nessa revisão. |
| HTTP | POST + GET (SSE) + DELETE da sessão; streams resumíveis com `Last-Event-ID` | POST com headers `MCP-Protocol-Version`, `Mcp-Method` e `Mcp-Name`. GET de stream e resumabilidade saem. Notificações de lista mudada vão para `subscriptions/listen`. |
| Transporte antigo | HTTP+SSE da revisão 2024-11-05 já tinha saído de uso | A especificação segue marcando esse HTTP+SSE como Deprecated. Este servidor já usa Streamable HTTP; essa linha não pede mudança. |
| Resultados | Resultado comum | Todo resultado tem `resultType` (`complete` ou `input_required`). |
| Features | Roots, sampling, logging no núcleo | Essas três entram em depreciação (SEP-2577). Diretório, arquivo e log ficam em config, argumento de tool ou stderr. |

O SDK Python passou à linha 2. A [guia de migração v1 → v2](https://py.sdk.modelcontextprotocol.io/v2/migration/) registra:

- `pip install mcp` instala 2.x. A linha 1 precisa de teto, por exemplo `mcp>=1.28,<2`.
- `from mcp.server.fastmcp import FastMCP` quebra: a classe passou a ser `MCPServer` em `mcp.server.mcpserver`.
- `host` e `port` saem do construtor e vão para `run()`.
- O SDK fala as duas eras. Código migrado continua atendendo clientes 2025-11-25. O comportamento novo (sem back-channel, `InputRequiredResult`, `subscriptions/listen`) só entra em conexões negociadas em 2026-07-28.
- `httpx` deixa de ser dependência do SDK (entra `httpx2`). Este repositório usa `httpx` no cliente Ollama, então o pacote continua no `requirements.txt` por conta própria.

O cliente do Cursor, em outubro de 2026, ainda fala **2025-11-25, 2025-06-18, 2025-03-26 e 2024-11-05**. Um servidor que aceita só 2026-07-28 rejeita o `initialize` e o painel MCP fica sem tools. Registro: [tópico do fórum](https://forum.cursor.com/t/mcp-client-cannot-connect-to-modern-only-2026-07-28-streamable-http-servers-legacy-initialize-rejected/172536). A equipe do Cursor indica servidor dual-era como o caminho que conecta hoje.

## Decisão

O servidor usa o SDK Python 2, com pin `mcp>=2,<3`, a classe `MCPServer` e o transporte Streamable HTTP. `MCP_HOST` e `MCP_PORT` são lidos do ambiente e passados a `run()`.

O exemplo de cliente no README é a revisão 2026-07-28: um POST, com `MCP-Protocol-Version`, `Mcp-Method` e `Mcp-Name`, e a versão repetida em `_meta`. Esse request não envia `initialize` nem `Mcp-Session-Id`.

O processo deixa o SDK no modo padrão do Streamable HTTP. Nesse modo o mesmo servidor aceita o handshake 2025-11-25 (`initialize` + `Mcp-Session-Id`) e a revisão 2026-07-28. O Cursor de hoje conecta, e um cliente da revisão nova fala o protocolo stateless na mesma porta.

As tools não guardam sessão de protocolo. O índice vive no Mongo. Qualquer identificador (documento, repositório, commit) entra como argumento comum da tool. `httpx` permanece no `requirements.txt` porque o cliente Ollama importa esse pacote.

Ficam de fora desta decisão: OAuth, `subscriptions/listen`, tasks, MRTR, e a exigência de que todo cliente fale só 2026-07-28. Roots, sampling e logging do protocolo não são usados.

## Consequências

- `server.py` importa `MCPServer`. No transporte HTTP, `run()` recebe host e porta.
- `requirements.txt` fixa `mcp>=2,<3` e mantém `httpx`.
- Um `tools/list` ou `tools/call` na revisão 2026-07-28 responde com `resultType: complete` e sem header de sessão.
- O mesmo processo responde ao handshake 2025-11-25.
- Troca de nomes de tools e o crawl seguem no `PLANO.md` e não fazem parte desta decisão. A escolha de modelo, contexto e teto de tokens está na [ADR 0002](0002-escolha-de-modelo.md).
