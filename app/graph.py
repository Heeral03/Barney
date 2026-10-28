from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from app.agents.curator import curator_node
from app.agents.memory import memory_in, memory_out
from app.agents.presenter import more_node, present_node, route_after_curator, route_after_more
from app.agents.requirements import requirements_node
from app.agents.researcher import fan_out, gather, plan_research, worker
from app.agents.supervisor import route_after_supervisor, supervisor_node
from app.agents.table import compare_node
from app.db import pool
from app.memory.store import ltm
from app.state import chatState

checkpointer = PostgresSaver(pool)
checkpointer.setup()  # creates the checkpoint tables on first run; a no-op afterwards

# START -> memory_in -> requirements -> memory_out -> supervisor -+-> (ask / chat) -> END
#          (recall)     (understand)   (save, trim)              |
#                                                               +-> plan_research -> worker x N (parallel) -> gather
#                                                               |        ^                                      |
#                                                               |        +---- fallback sources, once ----------+
#                                                               |                                               v
#                                                               |                                            curator -+-> present -> END
#                                                               +-> more <-------------------------------------------+ (mode "more")
#                                                                    |  ^ (nothing left: search again, appending)
#                                                                    +--+-> END
graph = StateGraph(chatState)
graph.add_node("memory_in", memory_in)  # subgraph: recall -> load
graph.add_node("requirements", requirements_node)  # understands the need; proposes search / ask / chat / more
graph.add_node("memory_out", memory_out)  # subgraph: commit (save what is worth keeping) -> shrink
graph.add_node("supervisor", supervisor_node)  # applies the guards and routes; no LLM
graph.add_node("plan_research", plan_research)
graph.add_node("worker", worker)
graph.add_node("gather", gather)
graph.add_node("curator", curator_node)
graph.add_node("present", present_node)
graph.add_node("more", more_node)
graph.add_node("compare", compare_node)  # side by side: normalised specs, fit with the shopper's needs, verified prices

graph.add_edge(START, "memory_in")
graph.add_edge("memory_in", "requirements")
graph.add_edge("requirements", "memory_out")
graph.add_edge("memory_out", "supervisor")
graph.add_conditional_edges(
    "supervisor", route_after_supervisor,
    {"plan_research": "plan_research", "more": "more", "compare": "compare", "__end__": END},
)
graph.add_conditional_edges("plan_research", fan_out, ["worker", "curator"])
graph.add_edge("worker", "gather")
graph.add_conditional_edges("gather", fan_out, ["worker", "curator"])
graph.add_conditional_edges("curator", route_after_curator, {"present": "present", "more": "more"})
graph.add_conditional_edges("more", route_after_more, {"plan_research": "plan_research", "__end__": END})
graph.add_edge("present", END)
graph.add_edge("compare", END)

chatbot = graph.compile(checkpointer=checkpointer, store=ltm)
