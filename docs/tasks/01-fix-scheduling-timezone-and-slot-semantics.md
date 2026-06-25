# Task — Corrigir semântica de timezone e unicidade dos slots disponíveis

Status: todo

## Restrição de overhead local

A correção deve manter o fluxo local simples: cálculo de timezone, testes
unitários e boot da API não podem exigir Redis, Docker, banco remoto ou serviço
externo. Casos de integração com banco/cache podem existir, mas devem continuar
separados por marcação/configuração opt-in e com fallback local claro.

## Problema

`ListProviderAvailableSlotsUseCase` combina `target_date` com horários locais e
produz datetimes naive, enquanto appointments são persistidos em colunas
timezone-aware. A normalização atual remove `tzinfo` do valor persistido sem
converter pelo timezone do provider. Apesar de `Provider.timezone` existir e
ser exposto pela API, ele não governa o cálculo. Isso funciona no timezone
local atual, mas pode comparar instantes errados para providers em outras zonas
ou nas transições de horário de verão.

Além disso, regras de disponibilidade sobrepostas adicionam o mesmo início mais
de uma vez porque `available_starts` é uma lista. A API também pode oferecer
slots passados quando a data consultada é hoje.

## Escopo

- Definir explicitamente se o contrato público recebe/devolve instantes UTC ou
  com offset e documentar a regra.
- Validar `Provider.timezone` com `zoneinfo.ZoneInfo` no cadastro; rejeitar nomes
  IANA inválidos.
- Calcular janelas no timezone do provider e converter limites/slots para UTC
  antes de consultar ou persistir.
- Remover `_normalize_slot_start` e `_normalize_persisted_datetime` baseados em
  simples remoção/adição de `tzinfo`.
- Deduplicar slots produzidos por regras sobrepostas e definir se sobreposição é
  permitida, rejeitada ou normalizada na escrita.
- Não oferecer horários já passados, usando uma porta de relógio injetável para
  que os testes não dependam do relógio real.
- Manter o banco como defesa final contra double booking.

## Fora do escopo

- Exceções de calendário, feriados e bloqueios manuais.
- Recorrência além das regras semanais atuais.
- Cancelamento ou remarcação.

## Plano

1. Especificar exemplos de conversão entre data local do provider e UTC.
2. Introduzir um pequeno value object/política de timezone no domínio de agenda.
3. Adaptar cálculo, consulta de slots ocupados e booking para uma representação
   canônica única.
4. Deduplicar candidatos e aplicar o corte de horários passados.
5. Atualizar cache: a chave deve continuar representando a data local do
   provider, enquanto o payload segue o contrato temporal escolhido.
6. Criar migration somente se a semântica das colunas precisar mudar; evitar
   regravar dados sem plano explícito.

## Testes

- Provider em `America/Fortaleza` e em uma zona com DST.
- Conversão na virada de dia UTC e em transição ambígua/inexistente de DST.
- Regra sobreposta não duplica horários.
- Data de hoje não retorna slots passados; data futura permanece estável.
- Booking e leitura de disponibilidade concordam sobre o mesmo instante.
- Cache hit e cache miss devolvem valores temporalmente equivalentes.

## Critérios de aceitação

- Nenhuma comparação temporal depende de apagar ou anexar `tzinfo` sem
  conversão.
- O timezone persistido é validado e efetivamente usado.
- A lista pública é ordenada, única e não contém horários passados.
- Testes unitários e de integração cobrem ao menos duas zonas e uma borda DST.
- README, contrato HTTP, livedoc e ADR 0005/0006 são revisados; criar ADR novo
  apenas se a semântica pública mudar materialmente.
