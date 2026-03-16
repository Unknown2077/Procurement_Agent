from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from src.agent.intents import IntentType, parse_intent
from src.agent.response_formatter import OutputContractValidator, format_response
from src.agent.skill_decision import decide_skill_usage
from src.config.runtime import RuntimeSkillPack
from src.data.adapter import DataAdapter
from src.llm.nim_client import NIMClient
from src.observability.trace_logger import TraceLogger
from src.tools.anomaly_detection import run_anomaly_detection
from src.tools.category_management import run_category_management
from src.tools.intelligent_recommendation import run_intelligent_recommendation
from src.tools.konsolidasi_pemaketan import run_konsolidasi_pemaketan


class OrchestratorState(TypedDict, total=False):
    query: str
    intent_value: str
    intent_result: Any
    skill_decision: Any
    data: list[dict[str, Any]]
    rules_triggered: list[str]
    reasoning: str
    response_payload: dict[str, Any]


@dataclass
class AgentOrchestrator:
    adapter: DataAdapter
    contract_validator: OutputContractValidator
    skill_pack: RuntimeSkillPack
    trace_logger: TraceLogger
    nim_client: NIMClient | None = None

    def handle_query(self, query: str) -> dict[str, Any]:
        if self.nim_client is None:
            raise RuntimeError(
                "NIM client is required for agent-driven routing. Set NIM_ENABLED=true."
            )
        if query.strip() == "":
            raise ValueError("Query cannot be empty.")

        graph = self._build_state_graph().compile()
        final_state: OrchestratorState = graph.invoke({"query": query})
        response_payload = final_state["response_payload"]
        self.trace_logger.log(
            {
                "query": query,
                "intent": response_payload["intent"],
                "skill_used": response_payload["skill_used"],
                "skill_reason": response_payload["skill_reason"],
                "confidence_score": response_payload["confidence_score"],
                "result_count": response_payload["result_count"],
            }
        )
        return response_payload

    def _build_state_graph(self) -> StateGraph:
        state_graph: StateGraph = StateGraph(OrchestratorState)
        state_graph.add_node("classify_query", self._node_classify_query)
        state_graph.add_node("decide_skill_usage", self._node_decide_skill_usage)
        state_graph.add_node("run_category", self._node_run_category)
        state_graph.add_node("run_anomaly", self._node_run_anomaly)
        state_graph.add_node("run_recommendation", self._node_run_recommendation)
        state_graph.add_node("run_consolidation", self._node_run_consolidation)
        state_graph.add_node("raise_unknown", self._node_raise_unknown)
        state_graph.add_node("format_validate", self._node_format_validate)
        state_graph.add_node("summarize", self._node_summarize)

        state_graph.set_entry_point("classify_query")
        state_graph.add_edge("classify_query", "decide_skill_usage")
        state_graph.add_conditional_edges(
            "decide_skill_usage",
            self._route_by_intent,
            {
                IntentType.CATEGORY_MANAGEMENT.value: "run_category",
                IntentType.ANOMALY_DETECTION.value: "run_anomaly",
                IntentType.INTELLIGENT_RECOMMENDATION.value: "run_recommendation",
                IntentType.KONSOLIDASI_PEMAKETAN.value: "run_consolidation",
                IntentType.UNKNOWN.value: "raise_unknown",
            },
        )
        state_graph.add_edge("run_category", "format_validate")
        state_graph.add_edge("run_anomaly", "format_validate")
        state_graph.add_edge("run_recommendation", "format_validate")
        state_graph.add_edge("run_consolidation", "format_validate")
        state_graph.add_edge("format_validate", "summarize")
        state_graph.add_edge("summarize", END)
        return state_graph

    def _node_classify_query(self, state: OrchestratorState) -> OrchestratorState:
        intent_result = parse_intent(query=state["query"], nim_client=self.nim_client)
        return {
            "intent_result": intent_result,
            "intent_value": intent_result.intent.value,
        }

    def _node_decide_skill_usage(self, state: OrchestratorState) -> OrchestratorState:
        intent_result = state["intent_result"]
        skill_decision = decide_skill_usage(
            query=state["query"],
            intent_result=intent_result,
            nim_client=self.nim_client,
        )
        return {"skill_decision": skill_decision}

    def _route_by_intent(self, state: OrchestratorState) -> str:
        return state["intent_value"]

    def _node_run_category(self, state: OrchestratorState) -> OrchestratorState:
        intent_result = state["intent_result"]
        data, rules_triggered, reasoning = run_category_management(
            query=state["query"],
            adapter=self.adapter,
            entities=intent_result.entities,
        )
        return {
            "data": data,
            "rules_triggered": rules_triggered,
            "reasoning": reasoning,
        }

    def _node_run_anomaly(self, state: OrchestratorState) -> OrchestratorState:
        data, rules_triggered, reasoning = run_anomaly_detection(
            query=state["query"],
            adapter=self.adapter,
        )
        return {
            "data": data,
            "rules_triggered": rules_triggered,
            "reasoning": reasoning,
        }

    def _node_run_recommendation(self, state: OrchestratorState) -> OrchestratorState:
        data, rules_triggered, reasoning = run_intelligent_recommendation(
            query=state["query"],
            adapter=self.adapter,
        )
        return {
            "data": data,
            "rules_triggered": rules_triggered,
            "reasoning": reasoning,
        }

    def _node_run_consolidation(self, state: OrchestratorState) -> OrchestratorState:
        data, rules_triggered, reasoning = run_konsolidasi_pemaketan(adapter=self.adapter)
        return {
            "data": data,
            "rules_triggered": rules_triggered,
            "reasoning": reasoning,
        }

    def _node_raise_unknown(self, state: OrchestratorState) -> OrchestratorState:
        raise RuntimeError(
            "Unknown intent returned by LLM classifier. "
            "Provide a procurement query matching supported intents."
        )

    def _node_format_validate(self, state: OrchestratorState) -> OrchestratorState:
        intent_result = state["intent_result"]
        skill_decision = state["skill_decision"]
        response_payload = format_response(
            intent=intent_result.intent.value,
            query=state["query"],
            data=state["data"],
            reasoning=state["reasoning"],
            rules_triggered=state["rules_triggered"],
            skill_used=skill_decision.use_feature_playbook,
            skill_reason=skill_decision.reason,
            confidence_score=skill_decision.confidence_score,
        )
        self.contract_validator.validate(response_payload)
        return {"response_payload": response_payload}

    def _node_summarize(self, state: OrchestratorState) -> OrchestratorState:
        skill_decision = state["skill_decision"]
        response_payload = state["response_payload"]
        response_payload["llm_summary"] = self._summarize_with_nim(
            response_payload=response_payload,
            use_feature_playbook=skill_decision.use_feature_playbook,
        )
        self.contract_validator.validate(response_payload)
        return {"response_payload": response_payload}

    def _summarize_with_nim(
        self,
        response_payload: dict[str, Any],
        use_feature_playbook: bool,
    ) -> str:
        instruction = self.skill_pack.core_policy
        if not use_feature_playbook:
            instruction = (
                "Use core response policy only.\n"
                + self.skill_pack.core_policy
            )
        prompt = (
            f"{instruction}\n\n"
            "Summarize the result in concise, factual English.\n"
            "You MUST only use information present in the payload.\n"
            "Do NOT add new analysis, assumptions, or actions outside the payload.\n"
            f"{json.dumps(response_payload, ensure_ascii=True)}"
        )
        summary: str = self.nim_client.summarize(prompt)
        if not self._is_summary_grounded(summary=summary, response_payload=response_payload):
            return self._build_deterministic_summary(response_payload=response_payload)
        return summary

    def _is_summary_grounded(
        self,
        summary: str,
        response_payload: dict[str, Any],
    ) -> bool:
        normalized_summary = summary.lower()
        allowed_text = (
            f"{response_payload.get('query', '')} "
            f"{response_payload.get('reasoning', '')} "
            f"{' '.join(response_payload.get('rules_triggered', []))}"
        ).lower()

        out_of_scope_by_intent: dict[str, tuple[str, ...]] = {
            IntentType.CATEGORY_MANAGEMENT.value: (
                "duplicate",
                "overlap",
                "consolidation",
                "anomaly",
            ),
            IntentType.INTELLIGENT_RECOMMENDATION.value: ("overlap", "consolidation"),
        }
        intent_value = str(response_payload.get("intent", ""))
        forbidden_terms = out_of_scope_by_intent.get(intent_value, ())
        return not any(
            term in normalized_summary and term not in allowed_text for term in forbidden_terms
        )

    def _build_deterministic_summary(self, response_payload: dict[str, Any]) -> str:
        intent = str(response_payload.get("intent", "unknown"))
        result_count = int(response_payload.get("result_count", 0))
        reasoning = str(response_payload.get("reasoning", "")).strip()
        result = response_payload.get("result", [])
        top_line = ""
        if isinstance(result, list) and result_count > 0 and isinstance(result[0], dict):
            first_item = result[0]
            package_name = str(first_item.get("nama_paket", "")).strip()
            package_id = str(first_item.get("id_paket", "")).strip()
            if package_name != "" and package_id != "":
                top_line = f" Top item: {package_name} ({package_id})."
        return (
            f"Intent {intent} returned {result_count} records."
            f" {reasoning}".strip()
            + top_line
        )
