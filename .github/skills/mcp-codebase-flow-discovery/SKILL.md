---
name: mcp-codebase-flow-discovery
description: "Use the configured MCP list_sources, search, and read tools to discover how a symbol, feature, API, module, event, or business rule flows through an indexed codebase. Trigger for code discovery, call-flow tracing, entry/exit analysis, or questions like where ScheduleCovid19Module is invoked and what rules it applies."
argument-hint: "Símbolo ou conceito para rastrear, fonte opcional e perguntas específicas"
---

# MCP Codebase Flow Discovery

Investigue código em fontes indexadas pelo MCP sem alterar arquivos. Reconstrua o fluxo com buscas e leituras sucessivas, mantendo cada conclusão ligada a evidências encontradas.

## Tools disponíveis

Use as tools MCP conectadas que correspondem a estes nomes; o cliente pode exibi-las com um prefixo do servidor:

- `list_sources()` — identifica as fontes disponíveis e seus IDs.
- `search(query, k=4, source_ids=None)` — encontra trechos semanticamente relacionados. Os resultados incluem texto e metadados como `source_id`, `path`, `chunk_index` e `score`.
- `read(source_id, path, start_line=None, end_line=None)` — lê o arquivo relativo à raiz da fonte; os limites de linha são inclusivos e começam em 1.

Se alguma tool necessária não estiver conectada, informe isso; não simule chamadas nem resultados.

## Procedimento

1. **Defina a pergunta.** Registre o símbolo ou conceito inicial e as dúvidas específicas: quem inicia, por onde passa, o que chama, onde termina e quais regras alteram o comportamento.
2. **Escolha a fonte.** Chame `list_sources()` e selecione o `id` apropriado, usando as indicações do usuário. Não confunda o ID da fonte com um commit hash. Se houver várias fontes plausíveis, pesquise nelas ou explique a escolha.
3. **Encontre o ponto inicial.** Faça uma busca pelo nome exato do símbolo. Para um identificador como `ScheduleCovid19Module`, faça também buscas direcionadas por variações de caixa/nome, nome de métodos, termos de registro e conceitos associados. Comece com `k=6` quando o resultado inicial estiver amplo; aumente se necessário.
4. **Extraia pistas dos resultados.** Anote cada par único `source_id` + `path`, símbolos e chamadas mencionadas. Trate `chunk_index` como índice de trecho, nunca como número de linha. O score ordena candidatos; não prova uma relação de chamada.
5. **Siga o fluxo iterativamente.** Mantenha uma fila de símbolos e caminhos ainda não investigados. Para cada candidato relevante, pesquise de forma específica por:
   - registro, importação, instanciação, injeção de dependência ou configuração;
   - rotas, controllers/handlers, eventos, jobs, schedulers ou comandos que possam iniciar o fluxo;
   - métodos chamados, serviços e clientes/dependências a jusante;
   - retornos, eventos emitidos, persistência, respostas e pontos de saída;
   - condições, validações, feature flags, permissões, retries e tratamentos de erro.
6. **Confirme com `read`.** Leia os arquivos dos resultados para verificar o contexto e a ordem real do código. Passe o `source_id` e o `path` exatamente como retornados. Prefira intervalos quando os números de linha forem conhecidos; sem limites, `read` retorna o arquivo inteiro e arquivos grandes podem gerar respostas extensas. Não trate o trecho de `search` como prova suficiente quando o contexto do arquivo for necessário.
7. **Repita com controle.** Adicione à fila os símbolos descobertos que ajudam a responder à pergunta; marque como visitados os pares `source_id` + símbolo e `source_id` + `path`. Por padrão, limite a exploração a 4 saltos de chamadas e 20 arquivos únicos, priorizando caminhos que ligam a entrada à saída. Amplie os limites se o usuário pedir uma investigação exaustiva.
8. **Finalize quando houver um caminho sustentado.** Pare quando entrada, principais etapas, saída e regras relevantes estiverem evidenciadas, ou quando novas buscas não encontrarem ligações úteis. Declare explicitamente os pontos que continuam sem confirmação.

## Evidência e limites

- Separe **confirmado no código**, **inferência** e **não encontrado**. Explique o raciocínio de qualquer inferência.
- Cite a origem e o caminho retornados pelo MCP. Só forneça números de linha se eles foram confirmados; nunca transforme `chunk_index` em linha nem invente localizações.
- A ferramenta `search` é semântica, não uma busca garantida de todas as referências. Busque nomes exatos e variantes, mas não declare que encontrou todas as chamadas sem uma verificação exaustiva independente.
- Essas tools consultam apenas as fontes indexadas e disponíveis ao servidor; não demonstram comportamento em runtime nem acessam automaticamente repositórios remotos fora dessas fontes.
- Se a fonte, o arquivo ou o símbolo não aparecer, relate a limitação e sugira o próximo passo (por exemplo, confirmar o ID, verificar se a fonte foi indexada ou fornecer outro termo/path). Não alegue que o código não existe com base em uma busca sem resultado.
- Não reproduza segredos ou credenciais que apareçam em trechos.

## Formato da resposta

Responda no idioma do usuário. Comece com um resumo curto e organize a descoberta assim:

1. **Entrada/acionamento** — origem e condição que inicia o fluxo.
2. **Caminho** — sequência numerada de módulos/funções, da entrada à saída.
3. **Saída/efeitos** — retorno, resposta, evento ou alteração observada.
4. **Regras** — validações e condições com impacto no caminho.
5. **Evidências e lacunas** — fontes/caminhos consultados e o que ainda não foi possível provar.

Use um diagrama Mermaid curto quando ajudar a visualizar as relações. Não force um diagrama se as evidências forem insuficientes.