DEFAULT_GRAPH_NAVIGATION_SYSTEM_MESSAGE = (
    "You are a knowledge graph navigation assistant. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_GRAPH_NAVIGATION_USER_TEMPLATE = """\
Query: {query}

Exploring node: "{current_label}" (type: {current_type})

Children:
{children_text}

Tasks:

1. coverage — how well can these children answer the query?
   - "full"    → ALL aspects of the query are completely answered by these children alone — set done=true
   - "partial" → some children are relevant, but the query likely has other aspects not covered here
   - "none"    → nothing here is relevant to the query

2. retrieved_ids — node_ids to immediately include in the answer set.
   - DATA nodes: include if their content directly answers the query.
   - CATEGORY nodes: only include if the category description itself is the answer.
   - Be selective — only include nodes that genuinely answer the query.

3. scores — confidence per child that its subtree contains the answer.
   - 0      → definitely irrelevant, prune entire subtree. Be aggressive — eliminate early.
   - 0.1–1.0 → probability this branch contains the answer.

Return ONLY valid JSON:
{{
  "coverage": "full" | "partial" | "none",
  "done": true | false,
  "retrieved_ids": ["<node_id>", ...],
  "scores": {{ "<node_id>": <number>, ... }},
  "reasoning": "<one concise sentence>"
}}\
"""


DEFAULT_GRAPH_SCORE_NODE_FOR_INSERTION_SYSTEM_MESSAGE = (
    "You are a knowledge graph placement assistant. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_GRAPH_SCORE_CATEGORY_NODE_FOR_INSERTION_USER_TEMPLATE = """\
Chunk to place:
{chunk}

{chunk_context_section}Exploring node: "{current_label}" (type: {current_type})

Category children to evaluate:
{children_text}

Task: For each category, determine whether the chunk belongs somewhere within that category's subtree.

Evaluate the specific facts, events, or concepts the chunk conveys — including what the preceding discussion \
context above (if given) says this chunk is reacting to, continuing, or building on. That continuation is itself \
a substantive fact about what the chunk is about, and counts toward the match even if the chunk's own wording \
doesn't restate it explicitly.
Disregard purely surface-level signals — who is speaking, how it is phrased, or incidental word overlap — those \
do not count on their own.

Score > 0 if the chunk's own specific facts, or the topic the preceding context says it continues from, fall \
clearly within the category's stated scope.
Score 0 otherwise.

Return ONLY valid JSON where each key is a node_id:
{{
  "<node_id>": {{ "score": <0-1>, "reasoning": "<3-4 sentences: what the chunk is specifically about, what the category covers, whether there is a concrete subject-matter match, and your conclusion>" }},
  ...
}}\
"""

DEFAULT_GRAPH_SCORE_DATA_NODE_FOR_INSERTION_USER_TEMPLATE = """\
Chunk to place:
{chunk}

{chunk_context_section}Data nodes to evaluate:
{children_text}

Task: For each data node, determine whether there is a direct reference relationship between the chunk and that node's content.
Score 1 if any of the following hold:
  - The chunk explicitly references specific content from this node, OR
  - This node's content explicitly references specific content from the chunk, OR
  - The preceding discussion context above (if given) establishes that this chunk is a direct continuation of, \
or reaction to, this node's specific content — even if the chunk's own wording doesn't restate it.
Score 0 if none of these hold — topical similarity or speaker framing alone does not count.

Return ONLY valid JSON where each key is a node_id:
{{
  "<node_id>": {{ "score": 0 | 1, "reasoning": "<one sentence>" }},
  ...
}}\
"""


DEFAULT_GENERATE_NODE_LABEL_SYSTEM_MESSAGE = (
    "You are a knowledge graph node labeling assistant. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_GENERATE_NODE_LABEL_USER_TEMPLATE = """\
Raw chunk:
{chunk}

Graph path(s) where this chunk will be placed:
{paths_text}

Generate a label and description for a new DATA node that will store this chunk.

Label (5–8 words): name the specific subject — include the key named entity, metric, or event. Avoid generic titles like "Discussion" or "Update" alone.

Description (1–2 sentences): act as a search index entry. Lead with the most specific identifiers — named people, organisations, product names, named metrics or topics discussed, dates, locations — so this node can be found by keyword. Do NOT include specific numeric values (dollar amounts, percentages, counts) — name the metric or topic being discussed, not its value; a value is too specific to help group or search for related content. Do not restate the label; add the concrete details that distinguish this node from any other.

{chunk_context_section}

Return ONLY valid JSON:
{{
  "label": "<5-8 word specific title>",
  "description": "<keyword-rich index entry with named entities and key facts>"
}}\
"""


DEFAULT_REORGANIZE_SYSTEM_MESSAGE = (
    "You are a knowledge graph reorganization assistant. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_GENERATE_UMBRELLA_CATEGORY_LABEL_SYSTEM_MESSAGE = (
    "You are a knowledge graph node labeling assistant. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_GENERATE_UMBRELLA_CATEGORY_LABEL_USER_TEMPLATE = """\
Parent node: "{parent_label}" (type: {parent_type})

These category nodes will all be grouped under a new super-category node:
{children_text}

Generate a concise label and 1–2 sentence description for the new super-category node.
- Label: 5–8 words naming the specific entity, event, or metric cluster — not a generic heading.
  Good: names the actual subject, key metric, or named event.  Bad: a vague topic like "Overview" or "Updates".
- Description: enumerate EVERY distinct topic, event, and named entity present across the grouped nodes — do not \
drop any of them in favor of only the most prominent one, even if it seems secondary. Name people, organisations, \
product names, named metrics or topics discussed, dates, named events. Do NOT include specific numeric values \
(dollar amounts, percentages, counts) — name the metric or topic, not its value.

Return ONLY valid JSON:
{{
  "label": "<5-8 word label>",
  "description": "<specific description>"
}}\
"""


DEFAULT_PROPOSE_REORGANIZE_GROUPS_USER_TEMPLATE = """\
Parent node: "{parent_label}" (type: {parent_type})

All child nodes to evaluate (including the new chunk being inserted, marked [NEW]):
{children_text}

Task, in two steps:
1. Propose candidate group labels for nodes that are semantically related enough to be grouped together. Nodes of any type may be grouped together.
2. Evaluate EVERY node listed above, one by one, including [NEW] — for each, decide which of your proposed groups it genuinely belongs to. A node may belong to more than one group if it is genuinely, specifically related to each — list every group it belongs to. Do not skip any node.

The node marked [NEW] is the chunk being inserted. Assign it to every group it is genuinely semantically related to, or an empty list if it does not fit well with any existing nodes.

Focus purely on semantic and subject-matter overlap between nodes' labels and descriptions.
Do NOT reason about child counts or capacity — that is handled separately by the system.

Label and description requirements for every proposed group:
- Label: 5–8 words, specific — name the actual subject, entity, or metric. Avoid generic words like "Discussion", "Overview", "Update" standing alone.
- Description: keyword-rich index entry. Enumerate EVERY distinct topic, event, and named entity present across \
the grouped nodes — do not drop any of them in favor of only the most prominent one, even if it seems secondary; \
a node placed under this group later will be found only if its specific topic is named here. Name people, \
organisations, product names, named metrics or topics discussed, dates, locations. Do NOT include specific \
numeric values (dollar amounts, percentages, counts) — name the metric or topic, not its value. Make it specific \
enough that a keyword search on any of those terms would find this group. Do not restate the label; add the \
concrete facts that distinguish this node.

Reasoning requirement: for every node's evaluation, give a detailed reason (2-3 sentences) for each group considered. Name the concrete shared facts — specific entities, topics, metrics, dates, or events — that the node and the group have in common, and state why those facts are specific enough to justify membership (or, if excluding, what is missing or mismatched). Do not write generic reasoning like "related topic" or "similar subject matter" — ground every claim in the actual content of the node and the group description.

{chunk_context_section}

Return ONLY valid JSON (return {{"groups": {{}}, "node_evaluations": {{}}}} if no meaningful groupings exist). Every node_id listed above must appear exactly once in "node_evaluations":
{{
  "groups": {{
    "<5-8 word label>": {{
      "description": "<keyword-rich index entry with named entities and key facts>"
    }}
  }},
  "node_evaluations": {{
    "<node_id>": {{
      "belongs_to": [
        {{"label": "<a group label above this node genuinely belongs to>", "reasoning": "<detailed reason, 2-3 sentences, naming the concrete shared facts that justify membership>"}}
      ]
    }}
  }}
}}
A node that fits no group gets "belongs_to": []. A node that genuinely fits multiple groups gets one entry per group, each with its own reasoning.\
"""


DEFAULT_EXTRACT_CHUNK_CONTEXT_SYSTEM_MESSAGE = (
    "You are a knowledge graph context analyst. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_EXTRACT_CHUNK_CONTEXT_USER_TEMPLATE = """\
Graph context so far (rolling summary of all prior chunks):
{graph_context}

New chunk:
{chunk}

Task:
1. Identify what named entities, events, facts, and concepts this chunk introduces.
2. Identify any references to entities or facts from prior chunks (cross-chunk references).
3. Write a "chunk_context": 2–3 sentences shaped as: this was being discussed — the preceding topic, entities, \
and thread of conversation, drawn from the graph context above — and then the current chunk came into picture. \
End by naming what the current chunk introduces relative to that preceding thread (a new topic, a continuation, \
a reaction to it), without restating or summarizing the new chunk's own content. Be concrete — names, dates, \
product names from that preceding discussion. This will be injected into downstream prompts to help interpret \
this chunk in light of what came before it.
4. Write "updated_graph_context": an updated rolling summary (max 400 words) that incorporates \
this chunk's new entities and facts. Preserve all prior named entities; do not drop earlier information.

Return ONLY valid JSON:
{{
  "chunk_context": "<2-3 sentences: the preceding discussion, then noting the current chunk came into picture>",
  "updated_graph_context": "<updated rolling summary, max 400 words>"
}}\
"""


DEFAULT_UPDATE_PARENT_NODE_LABEL_DESCRIPTION_SYSTEM_MESSAGE = (
    "You are a knowledge graph node labeling assistant. "
    "Always respond with valid JSON only — no markdown, no text outside the JSON object."
)

DEFAULT_UPDATE_PARENT_NODE_LABEL_DESCRIPTION_USER_TEMPLATE = """\
Existing category node:
Label: "{current_label}"
Description: {current_description}

A new piece of content is being placed beneath this node:
{chunk}

{chunk_context_section}
Task: Rewrite this node's label and description so they reflect that content like the new item \
above now genuinely belongs beneath this node — without simply appending the new information as \
an extra clause or sentence.

- Preserve every named entity, product, metric, or scope already captured in the existing label/description \
that is still accurate.
- Broaden or re-word only as needed so a reader scanning just the label/description would infer that \
content like the new item could plausibly live under this node.
- Do not narrate the update (no "now includes", "also covers", "in addition to", "and"-stitched clauses) — \
write it as if this had always been the node's natural scope.
- Label: 5–8 words, specific — name the actual subject, entity, or metric cluster. Avoid generic words \
like "Discussion", "Overview", "Update" standing alone.
- Description: 1–2 sentences, keyword-rich index entry style — named people, organisations, product names, \
named metrics or topics discussed, dates, locations. \
Do NOT include specific numeric values (dollar amounts, percentages, counts) — name the metric or topic, not its value; \
a value is too specific to help group or search for related content.
- If the new content is already fully covered by the existing label/description, return them unchanged.

Return ONLY valid JSON:
{{
  "label": "<5-8 word label>",
  "description": "<updated keyword-rich description>"
}}\
"""
