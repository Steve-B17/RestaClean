# from langgraph.graph import StateGraph, END
# from langgraph.graph.message import add_messages
# from pydantic import ValidationError
# from langchain_groq import ChatGroq
# from langchain_core.prompts import PromptTemplate
# from config import settings
# from langchain_core.messages import HumanMessage
# from models.schemas import CleanOrder, OrderInput, ErrorResponse
# from core.redis_client import redis_client
# import json
# from typing import TypedDict, Annotated, Optional
# import operator

# class CleaningState(TypedDict):
#     raw_text: str
#     validation_errors: list
#     attempt: int
#     messages: Annotated[list, add_messages]
#     final_result: Optional[dict]

# llm = ChatGroq(groq_api_key=settings.groq_api_key, model="meta-llama/llama-4-scout-17b-16e-instruct")

# def load_prompt(file_path: str) -> PromptTemplate:
#     with open(f"prompts/{file_path}") as f:
#         template = f.read()
#     return PromptTemplate.from_template(template)

# detect_prompt = load_prompt("detect_errors.txt")
# verify_prompt = load_prompt("verify_rules.txt")
# repair_prompt = load_prompt("repair_action.txt")

# def parse_raw(state: CleaningState) -> CleaningState:
#     """Parse raw WhatsApp text to JSON"""
#     prompt = detect_prompt.format(raw_text=state["raw_text"])
#     response = llm.invoke([HumanMessage(content=prompt)])
#     try:
#         parsed = json.loads(response.content)
#         return {"parsed_order": parsed, "attempt": 1}
#     except:
#         return {"parsed_order": None, "validation_errors": ["Parse failed"]}

# def validate_order(state: CleaningState) -> CleaningState:
#     """Validate with Pydantic + business rules"""
#     try:
#         order = CleanOrder(**state["parsed_order"])
#         return {"validation_errors": [], "final_result": order.model_dump()}
#     except ValidationError as e:
#         errors = [err["msg"] for err in e.errors()]
#         # Critical: Table# missing = immediate reject
#         if any("table_num" in err["loc"] for err in e.errors()):
#             return {
#                 "validation_errors": ["Table number missing - ask waiter"],
#                 "final_result": None
#             }
#         return {"validation_errors": errors}

# def reflect_and_repair(state: CleaningState) -> CleaningState:
#     """LLM fixes based on validation errors"""
#     if state["attempt"] >= 3:
#         return {"final_result": None, "validation_errors": ["Max attempts exceeded"]}
    
#     prompt = repair_prompt.format(
#         validation_errors=state["validation_errors"],
#         parsed_order=state["parsed_order"]
#     )
#     response = llm.invoke([HumanMessage(content=prompt)])
#     try:
#         fixed = json.loads(response.content)
#         return {"parsed_order": fixed, "attempt": state["attempt"] + 1}
#     except:
#         return {"final_result": None, "validation_errors": ["Repair failed"]}

# def should_continue(state: CleaningState) -> str:
#     """Routing logic"""
#     if state.get("final_result"):
#         return END
#     if "Table number missing" in str(state.get("validation_errors", [])):
#         return END  # Critical error - human needed
#     if state.get("attempt", 0) >= 3:
#         return END
#     return "repair"

# # Build LangGraph
# workflow = StateGraph(CleaningState)
# workflow.add_node("parse", parse_raw)
# workflow.add_node("validate", validate_order)
# workflow.add_node("repair", reflect_and_repair)

# workflow.set_entry_point("parse")
# workflow.add_edge("parse", "validate")
# workflow.add_conditional_edges("validate", should_continue, {
#     "repair": "repair",
#     END: END
# })
# workflow.add_edge("repair", "validate")

# cleaner = workflow.compile()

# async def clean_order(raw_text: str) -> dict:
#     """Main cleaning function"""
#     result = await cleaner.ainvoke({  # ← ADD 'await' HERE
#         "raw_text": raw_text,
#         "attempt": 0,
#         "messages": []
#     })
    
#     if result["final_result"]:
#         return {
#             "success": True,
#             "order": result["final_result"],
#             "attempts": result["attempt"]
#         }
#     else:
#         return {
#             "success": False,
#             "error": result["validation_errors"][0] if result["validation_errors"] else "Unknown error",
#             "suggestion": "Please check order format"
#         }

from config import settings
from typing import Dict, Any, TypedDict
from pydantic import ValidationError, Field
from langchain_groq import ChatGroq
from models.schemas import CleanOrder
import json

# Simple TypedDict state (NO LangGraph complexity)
class CleaningState(TypedDict):
    raw_text: str
    table_num: int
    items: list
    total_amount: float
    success: bool
    error: str

llm = ChatGroq(groq_api_key=settings.groq_api_key, model="openai/gpt-oss-20b")

async def clean_order(raw_text: str) -> Dict[str, Any]:
    """SIMPLE LLM cleaning - NO LangGraph complexity"""
    
    # Step 1: LLM Parse raw text
    prompt = f"""
    Parse this restaurant WhatsApp order to JSON:
    "{raw_text}"
    
    Rules:
    - Table 1-20 (MANDATORY)
    - Items: Idly(₹30), Dosa(₹110), Vada(₹30)  
    - Output ONLY valid JSON
    
    Example: "table 5 3 idly" → {{"table_num":5,"items":[{{"name":"Idly","qty":3}}],"total_amount":90}}
    """
    
    try:
        response = llm.invoke(prompt)
        parsed = json.loads(response.content.strip())
        
        # Step 2: Validate business rules
        table_num = parsed.get("table_num")
        if not table_num or not (1 <= table_num <= 20):
            return {
                "success": False,
                "error": "Table number missing or invalid (must be 1-20)",
                "suggestion": "Please add Table# (1-20)"
            }
        
        # Step 3: Fix items + calculate total
        items = parsed.get("items", [])
        total = 0
        fixed_items = []
        
        for item in items:
            name = item.get("name", "Idly").title()
            qty = int(item.get("qty", 1))
            
            # Restaurant price rules
            price_map = {"Idly": 32, "Dosa": 110, "Vada": 30, "Coffee": 25}
            price = price_map.get(name, 50)  # Default ₹50
            
            fixed_items.append({
                "name": name,
                "qty": qty,
                "price": price
            })
            total += qty * price
        
        return {
            "success": True,
            "order": {
                "table_num": table_num,
                "items": fixed_items,
                "total_amount": round(total, 2)
            },
            "attempts": 1
        }
        
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Cannot parse order format",
            "suggestion": "Use: 'table 5 3 idly total 95'"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Processing error: {str(e)}",
            "suggestion": "Please check order format"
        }
