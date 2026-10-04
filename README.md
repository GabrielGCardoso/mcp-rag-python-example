# Vector Search — RAG local (Python + SQLite)

Servidor MCP que indexa documentação e responde com busca vetorial. O índice é um arquivo SQLite. Não precisa de Docker nem de um banco separado.

| Tool | O que faz |
|------|-----------|
| `list_sources` | Fontes, último crawl, commit, contagem de chunks, erro da última rodada |
| `search` | Trechos parecidos com a consulta (cosseno + MMR), com `source_id`, path e score. Sem LLM |
| `read` | Abre um arquivo da fonte, inteiro ou num intervalo de linhas |
| `ask` | Só existe se `OLLAMA_CHAT_MODEL` estiver definido. Busca + redação via Ollama |

Na discovery, quem redige é o modelo do editor. `search` e `read` bastam.

## Setup

Python 3.12.

### Instalar o venv

No Ubuntu o módulo `venv` é um pacote separado:

```bash
sudo apt install python3-venv
```

Na pasta do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/crawl.py
```

`source .venv/bin/activate` vale para o terminal atual: a partir daí `python` e `pip` são os do `.venv`. Os comandos seguintes usam `.venv/bin/python`, que aponta para o mesmo ambiente. O índice fica em `data/index.sqlite`.

A primeira indexação baixa o modelo ONNX `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (o padrão de `EMBED_BACKEND=local`, cerca de 220 MB). `sources.yaml` aponta o exemplo para `fcc_docs/`.

`scripts/embed_docs.py` faz o mesmo crawl, só nas fontes `kind: local`.

### Docker

O Compose sobe o Ollama e o servidor HTTP. O índice vai para o volume `index_data` (`/data/index.sqlite` dentro do `docs-mcp`). O `docs-mcp` fala com o Ollama pelo nome `ollama` na rede do Compose. No host, esse Ollama escuta em `localhost:11435`.

Na pasta do projeto:

```bash
docker compose up -d
docker compose exec ollama ollama pull nomic-embed-text
docker compose run --rm docs-mcp python scripts/crawl.py
```

O `up` deixa o MCP em `http://localhost:8000/mcp`. O `pull` baixa a tag no serviço `ollama`. O `run` indexa `fcc_docs/` nesse volume. Um crawl novo usa o mesmo `OLLAMA_EMBED_MODEL` do servidor. O default é `nomic-embed-text`.

Para outra tag, exporte `OLLAMA_EMBED_MODEL` e `OLLAMA_CHAT_MODEL` antes do `up` e recrie o `docs-mcp`. O `up` grava essas variáveis na criação do container. `scripts/pull-docker-ollama-models.sh` faz o `ollama pull` das duas.

### Editor

O transporte padrão é stdio. O Cursor sobe o processo. Exemplo em [`.vscode/mcp.json`](.vscode/mcp.json):

```json
{
  "servers": {
    "docs-mcp": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["server.py"]
    }
  }
}
```

O diretório de trabalho do servidor precisa ser a pasta do projeto.

## Fontes

```yaml
sources:
  - id: fcc-docs
    kind: local
    path: fcc_docs
    include: ["**/*.md"]
  - id: payments
    kind: git
    url: git@github.com:org/payments.git
    branch: main
    include: ["**/*.md", "**/*.mdx", "**/README*"]
    exclude: ["**/.git/**", "**/node_modules/**", "**/dist/**", "**/*lock*"]
```

O clone git vai para `data/sources/<id>/`. Credencial por SSH agent ou token no ambiente, nunca no YAML. O crawl é manual:

```bash
.venv/bin/python scripts/crawl.py
```

Arquivo com o mesmo hash e o mesmo modelo de embedding é pulado. Hash novo, modelo novo ou arquivo removido atualiza só aquele path.

O `include` decide o que entra. Markdown usa o splitter de markdown. `.py`, `.js`, `.ts`, `.go`, `.java` e `.rs` usam o splitter da linguagem, com teto de 400 caracteres. O exemplo do repositório indexa só `**/*.md`.

## Escolher o modelo

Há dois papéis. O embedding é o que a busca usa. O chat entra na tool `ask`, que redige uma resposta a partir dos trechos já recuperados. No editor, quem explora a documentação é o modelo do Cursor.

O padrão, se você não exportar nada, é o embedder local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. O `fastembed` 0.8 não publica o E5 small; o E5 large pesa 2,2 GB. Este MiniLM cabe em CPU, pesa cerca de 220 MB e cobre português e inglês. A tool `ask` não sobe enquanto `OLLAMA_CHAT_MODEL` estiver vazio.

`EMBED_BACKEND=ollama` usa o Ollama que já estiver em `OLLAMA_BASE_URL` (o binário nativo, ou o serviço do Compose). Aí a tag vem de `OLLAMA_EMBED_MODEL`. O par citado abaixo, `nomic-embed-text` e `llama3.2:3b`, é o ponto de partida desse backend para o `fcc_docs/` atual: markdown curto, em inglês. Para português, código ou arquivo longo, os perfis trocam a tag sem mudar código.

Trocar o modelo de embedding muda a dimensão do vetor. Rode o crawl de novo. Uma busca só lê vetores gravados com o modelo ativo.

O contexto da coluna é a janela publicada da tag. `EMBED_NUM_CTX` limita o quanto entra em cada trecho (em tokens; o splitter usa cerca de 4 caracteres por token). `OLLAMA_NUM_CTX` é a janela do chat. `OLLAMA_NUM_PREDICT` é o teto de tokens da resposta. Sem essas variáveis, o chunk fica em 500 caracteres e o Ollama usa o default da tag. A decisão está em [docs/adr/0002-escolha-de-modelo.md](docs/adr/0002-escolha-de-modelo.md).

Fontes das fichas: [qwen3-embedding](https://ollama.com/library/qwen3-embedding), [nomic-embed-text](https://ollama.com/library/nomic-embed-text), [qwen3](https://ollama.com/library/qwen3).

### Embedding

| Tag | Tamanho | Contexto | Melhor quando |
| --- | --- | --- | --- |
| `paraphrase-multilingual-MiniLM-L12-v2` | 220 MB, ONNX | 512 | Padrão. `EMBED_BACKEND=local`, sem daemon. |
| `nomic-embed-text` | 274 MB | 2K | Backend Ollama. Corpus curto em inglês e pouca RAM. É o caso do `fcc_docs/`. |
| `qwen3-embedding:0.6b` | 639 MB | 32K | Máquina de trabalho sem GPU, documentação em português, código ou README longo. |
| `qwen3-embedding:4b` | 2,5 GB | 40K | Há RAM (e de preferência GPU) e o trecho a indexar passa da janela de 32K. |
| `qwen3-embedding:8b` | 4,7 GB | 40K | Mesmo caso do 4B, quando a qualidade do retrieval pesa mais que o tamanho. |

`embeddinggemma` (cerca de 622 MB, contexto 2048) fica de fora: a janela curta corta arquivo de código e README longo.

No backend Ollama, o cliente aplica `search_query:` / `search_document:` no `nomic-embed-text`, e a instrução de retrieval na consulta do `qwen3-embedding`.

### Chat

Só importa se `OLLAMA_CHAT_MODEL` estiver definido.

| Tag | Tamanho | Contexto | Melhor quando |
| --- | --- | --- | --- |
| `llama3.2:3b` | 2,0 GB | 128K | `ask` em inglês, no corpus atual. |
| `qwen3:1.7b` | 1,4 GB | 40K | A máquina já roda embedding e sobra pouca RAM. |
| `qwen3:4b` | 2,5 GB | 256K | Resposta em português sobre trechos já buscados, sem GPU dedicada. |
| `qwen3:8b` | 5,2 GB | 40K | A resposta redigida localmente precisa de mais qualidade e a RAM cobre o peso. |

O cliente de chat envia `num_gpu: 0`, então o modelo de chat precisa caber na RAM mesmo que a máquina tenha GPU. O embedding do Ollama usa o que o serviço tiver disponível.

### Comandos

Ollama nativo, sem Docker. O processo do Ollama já precisa estar no ar.

Corpus curto em inglês:

```bash
export EMBED_BACKEND=ollama
export OLLAMA_EMBED_MODEL=nomic-embed-text
.venv/bin/python scripts/crawl.py
```

Português, código ou arquivo longo, máquina de trabalho sem GPU. Trocar a tag de embedding exige reindexar:

```bash
export EMBED_BACKEND=ollama
export OLLAMA_EMBED_MODEL=qwen3-embedding:0.6b
export OLLAMA_CHAT_MODEL=qwen3:4b
ollama pull "$OLLAMA_EMBED_MODEL"
ollama pull "$OLLAMA_CHAT_MODEL"
.venv/bin/python scripts/crawl.py
```

Mais qualidade, com RAM para os pesos maiores:

```bash
export EMBED_BACKEND=ollama
export OLLAMA_EMBED_MODEL=qwen3-embedding:4b
export OLLAMA_CHAT_MODEL=qwen3:8b
ollama pull "$OLLAMA_EMBED_MODEL"
ollama pull "$OLLAMA_CHAT_MODEL"
.venv/bin/python scripts/crawl.py
```

Trocar só o chat dispensa o crawl. Exemplo, mantendo o embedding local e ligando o `ask`:

```bash
export OLLAMA_CHAT_MODEL=qwen3:4b
ollama pull "$OLLAMA_CHAT_MODEL"
```

Para fixar o par entre sessões, grave as variáveis no `.env` (a partir de [`.env.example`](.env.example)).

## Variáveis de ambiente

| Variável | Default | Papel |
|----------|---------|--------|
| `EMBED_BACKEND` | `local` | `local` (ONNX) ou `ollama` |
| `LOCAL_EMBED_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo do backend local |
| `SQLITE_PATH` | `data/index.sqlite` | Arquivo do índice |
| `SOURCES_FILE` | `sources.yaml` | Lista de fontes |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama nativo ou do Compose |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Tag quando o backend é `ollama` |
| `OLLAMA_CHAT_MODEL` | vazio | Vazio não registra `ask` |
| `EMBED_NUM_CTX` | vazio | Tokens por trecho. Vazio = chunk de 500 caracteres |
| `OLLAMA_NUM_CTX` | vazio | Janela do chat |
| `OLLAMA_NUM_PREDICT` | vazio | Teto de tokens da resposta |
| `MCP_TRANSPORT` | `stdio` | `stdio` ou `streamable-http` |

## HTTP opcional

Com `MCP_TRANSPORT=streamable-http` o servidor escuta em `http://localhost:8000/mcp`. O exemplo abaixo é a revisão 2026-07-28: um POST, sem `initialize` e sem `Mcp-Session-Id`.

```bash
MCP=http://localhost:8000/mcp

curl -s -X POST "$MCP" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2026-07-28" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: search" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search","arguments":{"query":"How do I open a pull request?","k":4},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"curl","version":"1.0"}}}}'
```

## Estrutura

```
vector-search/
├── server.py              # MCP: list_sources, search, read, ask
├── sources.yaml           # fontes locais e git
├── lib/                   # SQLite, crawl, embedding, busca
├── scripts/
│   ├── crawl.py                      # indexação incremental
│   ├── embed_docs.py                 # só fontes locais
│   └── pull-docker-ollama-models.sh  # ollama pull no serviço do Compose
├── fcc_docs/                         # corpus de exemplo
└── compose.yml                       # Ollama + servidor HTTP
```

## Testes

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

Os testes não baixam modelo nem falam com o Ollama. A busca usa vetores fixos.

## Créditos e referências

Este módulo reutiliza a documentação em `fcc_docs/` e o fluxo RAG do workshop, adaptados do repositório [beaucarnes/vector-search-tutorial](https://github.com/beaucarnes/vector-search-tutorial).

- **Dados e tutorial base:** [github.com/beaucarnes/vector-search-tutorial](https://github.com/beaucarnes/vector-search-tutorial)
- **Workshop original:** [Let AI Be Your Docs](https://github.com/mongodb-developer/vector-search-workshop)
