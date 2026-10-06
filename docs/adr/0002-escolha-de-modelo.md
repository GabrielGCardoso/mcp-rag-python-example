# ADR 0002 — O operador escolhe o modelo de embedding e o contexto

- Status: aceita
- Data: 2026-10-03

## Contexto

O servidor usa um modelo só para produzir o vetor da busca. Quem redige a resposta no editor é o modelo do cliente MCP, a partir de `search` e `read`.

A tag vem do ambiente: `OLLAMA_EMBED_MODEL` (default `nomic-embed-text`) quando `EMBED_BACKEND=ollama`. O Compose e `scripts/pull-docker-ollama-models.sh` leem essa tag. Sem `EMBED_NUM_CTX`, o chunk fica em 500 caracteres.

A máquina de quem sobe o serviço não é uma só. Há CPU de trabalho sem GPU, host apertado, e máquina com RAM ou GPU de sobra. O corpus também muda: markdown curto em inglês, documentação em português, código, README longo. A janela do embedding corta o trecho que vira vetor. Uma tag fixa na imagem não cobre esses casos.

## Decisão

Quem roda o servidor escolhe, pela configuração de ambiente:

1. O modelo de embedding, de acordo com a máquina (RAM, GPU, o que mais já está no host) e com o corpus (idioma, código, tamanho do arquivo).
2. Quanto contexto usar: quantos tokens entram no embedding de cada trecho.

A imagem não grava uma tag. O repositório mantém um default para subir sem configurar nada, e o README publica o perfil recomendado para cada máquina, com o comando e as variáveis. Trocar o modelo de embedding exige reindexar: a dimensão do vetor muda, e vetores de modelos diferentes não entram na mesma busca.

O guia operacional — tabela, em qual caso cada tag é melhor, comando completo — fica só no README. Este registro não escolhe a tag da POC.

Não há tool de chat. A redação fica no modelo do editor.

## Consequências

- `OLLAMA_EMBED_MODEL` é a forma de escolher a tag no backend Ollama. Vale no Compose, no `.env` e no script de pull.
- `EMBED_NUM_CTX` é a janela do embedding. Sem valor, o chunk fica em 500 caracteres.
- Uma busca usa apenas vetores gravados com o mesmo modelo de embedding. Trocar a tag sem reindexar não é um modo suportado.
- O `PLANO.md` não repete a tabela nem os comandos. O crawl e o nome das tools continuam naquele arquivo.
- Nesta versão o backend padrão de embedding é `local` (`EMBED_BACKEND`). `OLLAMA_EMBED_MODEL` vale quando `EMBED_BACKEND=ollama`.
