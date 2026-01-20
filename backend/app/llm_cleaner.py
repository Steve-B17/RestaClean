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
# -------------
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
# PRICE_MAP = {
#     "Idly": 32,
#     "Dosa": 110, 
#     "Vada": 30,
#     "Coffee": 25
# }
# # ✅ FIX 1: Add missing parsed_order field
# class CleaningState(TypedDict):
#     raw_text: str
#     parsed_order: Optional[dict]  # ← ADDED THIS
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
#     """Parse + Apply price rules"""
#     prompt = detect_prompt.format(raw_text=state["raw_text"])
#     response = llm.invoke([HumanMessage(content=prompt)])
    
#     try:
#         parsed = json.loads(response.content)
        
#         # ✅ AUTO-APPLY YOUR PRICES
#         items = parsed.get("items", [])
#         for item in items:
#             item_name = str(item.get("name", "")).lower().strip()
#             if item_name in PRICE_MAP:
#                 item["name"] = item_name.capitalize()
#                 item["price"] = PRICE_MAP[item["name"]]
#                 print(f"✅ Fixed {item['name']} price to ₹{item['price']}")
        
#         # Auto-calculate total
#         if parsed.get("items") and not parsed.get("total_amount"):
#             total = sum(item.get("qty", 0) * item.get("price", 0) for item in items)
#             parsed["total_amount"] = round(total, 2)
        
#         return {"parsed_order": parsed, "attempt": 1}
#     except:
#         return {"parsed_order": None, "validation_errors": ["Parse failed"]}

# def validate_order(state: CleaningState) -> CleaningState:
#     """Validate with Pydantic + business rules"""
#     # ✅ FIX 3: Safe parsed_order access
#     parsed_order = state.get("parsed_order")
#     if not parsed_order:
#         return {
#             "validation_errors": ["No parsed order"],
#             "final_result": None
#         }
    
#     try:
#         order = CleanOrder(**parsed_order)
#         return {"validation_errors": [], "final_result": order.model_dump()}
#     except ValidationError as e:
#         errors = [err["msg"] for err in e.errors()]
#         # Critical: Table# missing = immediate reject
#         if any("table_num" in str(err["loc"]) for err in e.errors()):
#             return {
#                 "validation_errors": ["Table number missing - ask waiter"],
#                 "final_result": None
#             }
#         return {"validation_errors": errors}

# def reflect_and_repair(state: CleaningState) -> CleaningState:
#     """LLM fixes - clears errors to break loop"""
#     if state.get("attempt", 0) >= 2:
#         return {"final_result": None, "validation_errors": ["Max attempts exceeded"]}
    
#     parsed_order = state.get("parsed_order", {})
#     validation_errors = state.get("validation_errors", [])
    
#     prompt = repair_prompt.format(
#         validation_errors=validation_errors,
#         parsed_order=json.dumps(parsed_order)
#     )
#     response = llm.invoke([HumanMessage(content=prompt)])
#     try:
#         fixed = json.loads(response.content)
#         return {
#             "parsed_order": fixed, 
#             "attempt": state.get("attempt", 0) + 1,
#             "validation_errors": []  # ← BREAKS LOOP
#         }
#     except:
#         return {"final_result": None, "validation_errors": ["Repair failed"]}

# def should_continue(state: CleaningState) -> str:
#     """Routing logic - MAX 2 iterations (parse + 1 repair)"""
#     if state.get("final_result"):
#         return END
#     if "Table number missing" in str(state.get("validation_errors", [])):
#         return END
#     if state.get("attempt", 0) >= 2:  # 1 parse + 1 repair = STOP
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
#     result = await cleaner.ainvoke({
#         "raw_text": raw_text,
#         "attempt": 0,
#         "messages": [],
#         "parsed_order": None,  # ✅ FIX 5: Initialize all fields
#         "validation_errors": [],
#         "final_result": None
#     },{ "recursion_limit": 4 })
    
#     # ✅ FIX 6: Safe final result access
#     final_result = result.get("final_result")
#     if final_result:
#         return {
#             "success": True,
#             "order": final_result,
#             "attempts": result.get("attempt", 0)
#         }
#     else:
#         errors = result.get("validation_errors", ["Unknown error"])
#         return {
#             "success": False,
#             "error": errors[0] if errors else "Unknown error",
#             "suggestion": "Please check order format"
#         }
# -----------

# from config import settings
# from typing import Dict, Any, TypedDict
# from pydantic import ValidationError, Field
# from langchain_groq import ChatGroq
# from models.schemas import CleanOrder
# import json

# # Simple TypedDict state (NO LangGraph complexity)
# class CleaningState(TypedDict):
#     raw_text: str
#     table_num: int
#     items: list
#     total_amount: float
#     success: bool
#     error: str

# llm = ChatGroq(groq_api_key=settings.groq_api_key, model="openai/gpt-oss-20b")

# async def clean_order(raw_text: str) -> Dict[str, Any]:
#     """SIMPLE LLM cleaning - NO LangGraph complexity"""
    
#     # Step 1: LLM Parse raw text
#     prompt = f"""
#     Parse this restaurant WhatsApp order to JSON:
#     "{raw_text}"
    
#     Rules:
#     - Table 1-20 (MANDATORY)
#     - Items: Idly(₹30), Dosa(₹110), Vada(₹30)  
#     - Output ONLY valid JSON
    
#     Example: "table 5 3 idly" → {{"table_num":5,"items":[{{"name":"Idly","qty":3}}],"total_amount":90}}
#     """
    
#     try:
#         response = llm.invoke(prompt)
#         parsed = json.loads(response.content.strip())
        
#         # Step 2: Validate business rules
#         table_num = parsed.get("table_num")
#         if not table_num or not (1 <= table_num <= 20):
#             return {
#                 "success": False,
#                 "error": "Table number missing or invalid (must be 1-20)",
#                 "suggestion": "Please add Table# (1-20)"
#             }
        
#         # Step 3: Fix items + calculate total
#         items = parsed.get("items", [])
#         total = 0
#         fixed_items = []
        
#         for item in items:
#             name = item.get("name", "Idly").title()
#             qty = int(item.get("qty", 1))
            
#             # Restaurant price rules
#             price_map = {"Idly": 32, "Dosa": 110, "Vada": 30, "Coffee": 25}
#             price = price_map.get(name, 50)  # Default ₹50
            
#             fixed_items.append({
#                 "name": name,
#                 "qty": qty,
#                 "price": price
#             })
#             total += qty * price
        
#         return {
#             "success": True,
#             "order": {
#                 "table_num": table_num,
#                 "items": fixed_items,
#                 "total_amount": round(total, 2)
#             },
#             "attempts": 1
#         }
        
#     except json.JSONDecodeError:
#         return {
#             "success": False,
#             "error": "Cannot parse order format",
#             "suggestion": "Use: 'table 5 3 idly total 95'"
#         }
#     except Exception as e:
#         return {
#             "success": False,
#             "error": f"Processing error: {str(e)}",
#             "suggestion": "Please check order format"
#         }
# ---------------------
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import ValidationError, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.core.config import settings
from langchain_core.messages import HumanMessage
from app.schemas.order import CleanOrder
import json
import re
from typing import TypedDict, Annotated, Optional, Dict, Any, List
import operator

# ✅ Restaurant menu with exact prices
PRICE_MAP = {
    "Idly": 15,
    "Dosa": 10, 
    "Vada": 10,
    "Coffee": 25
}

class CleaningState(TypedDict):
    raw_text: str
    parsed_order: Optional[dict]
    validation_errors: list[str]
    attempt: int
    messages: Annotated[list, add_messages]
    final_result: Optional[dict]
    error_type: Optional[str]
    existing_order: Optional[dict]  # For merging logic

llm = ChatGroq(
    groq_api_key=settings.groq_api_key, 
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    temperature=0  # Deterministic parsing
)

# ✅ DETECT PROMPT - Strict parsing with NO assumptions
detect_prompt = PromptTemplate.from_template("""
Extract order details from this text. Follow rules EXACTLY.

Text: {raw_text}

STRICT RULES:
1. Table keyword MUST exist: "table", "Table", "TABLE", "Table#", "table#"
   - "tbl" is NOT valid → Return {{"error": "NO_TABLE_FOUND"}}
   - If no table keyword → Return {{"error": "NO_TABLE_FOUND"}}

2. Table number MUST be 1-20
   - "table 0" → Return {{"error": "INVALID_TABLE", "reason": "Table must be 1-20"}}
   - "table abc" → Return {{"error": "INVALID_TABLE", "reason": "Table must be a number"}}

3. Quantity MUST be positive integer before item
   - "3 idly" = qty 3 ✓
   - "idly" (no number) → Return {{"error": "NO_QUANTITY_FOUND", "table_num": X}}
   - "-1 idly" → Return {{"error": "INVALID_QUANTITY", "table_num": X}}
4. Extract ALL items mentioned

EXAMPLES:
"table 5 3 idly" → {{"table_num": 5, "items": [{{"name": "Idly", "qty": 3}}], "total_amount": 0}}
"table 10 4 vada 2 coffee" → {{"table_num": 10, "items": [{{"name": "Vada", "qty": 4}}, {{"name": "Coffee", "qty": 2}}], "total_amount": 0}}
"table 5 idly" → {{"error": "NO_QUANTITY_FOUND", "table_num": 5}}
"8 idly" → {{"error": "NO_TABLE_FOUND"}}
"tbl 5 2 dosa" → {{"error": "NO_TABLE_FOUND"}}
"table 0 3 idly" → {{"error": "INVALID_TABLE", "reason": "Table must be 1-20"}}
"table 5 -1 idly" → {{"error": "INVALID_QUANTITY", "table_num": 5}}

CRITICAL: Output ONLY JSON. Start with {{ end with }}. No markdown, no explanation.
""")

# ✅ REPAIR PROMPT - Fix correctable errors
repair_prompt = PromptTemplate.from_template("""
Fix this order using restaurant prices.

Broken order: {parsed_order}
Errors: {validation_errors}

MENU PRICES: Idly=₹15, Dosa=₹10, Vada=₹10, Coffee=₹25

FIX RULES:
- Apply correct prices from menu
- Unknown items → ₹50 default
- Recalculate total_amount = SUM(qty × price)
- Keep table_num unchanged if valid (1-20)
- Keep quantities unchanged

Output ONLY fixed JSON (no markdown):
{{"table_num": 5, "items": [{{"name": "Idly", "qty": 3, "price": 15}}], "total_amount": 45}}
""")

def apply_restaurant_prices(items: list) -> tuple[list[dict], float]:
    """Apply menu prices and calculate total"""
    fixed_items = []
    total = 0
    
    for item in items:
        name = str(item.get("name", "")).strip().title()
        if not name:
            continue
            
        qty = int(item.get("qty", 1))
        if qty < 1:
            qty = 1
        
        # Use menu price or default ₹50 for unknown items
        price = PRICE_MAP.get(name, 50)
        
        fixed_items.append({
            "name": name,
            "qty": qty,
            "price": price
        })
        total += qty * price
    
    return fixed_items, round(total, 2)

def regex_precheck(raw_text: str) -> Optional[Dict[str, Any]]:
    """Pre-parse validation using regex for speed"""
    text = raw_text.lower().strip()
    
    # Check 1: Table keyword must exist
    if not re.search(r'\btable\b|table#|table\s*\d+', text):
        return {"error": "NO_TABLE_FOUND"}
    
    # Check 2: Extract table number
    table_match = re.search(r'table[#\s]*(\d+)', text)
    if not table_match:
        return {"error": "NO_TABLE_FOUND"}
    
    table_num = int(table_match.group(1))
    
    # Check 3: Table range validation
    if table_num < 1 or table_num > 20:
        return {"error": "INVALID_TABLE", "table_num": table_num, "reason": "Table must be 1-20"}
    
    # Check 4: Empty order (no items)
    if not re.search(r'\d+\s+(idly|dosa|vada|coffee)', text, re.IGNORECASE):
        return {"error": "NO_ITEMS", "table_num": table_num}
    
    return None  # Pass to LLM

def parse_raw(state: CleaningState) -> CleaningState:
    """STEP 1: DETECT - Parse raw WhatsApp text"""
    print(f"\n🔍 DETECT: '{state['raw_text']}'")
    
    # Fast regex pre-check
    precheck_error = regex_precheck(state['raw_text'])
    if precheck_error:
        error_code = precheck_error.get("error")
        print(f"❌ PRE-CHECK FAILED: {error_code}")
        
        if error_code == "NO_TABLE_FOUND":
            return {
                "parsed_order": None,
                "validation_errors": ["Table number is missing. Use 'table [number]'"],
                "error_type": "missing_table",
                "final_result": None
            }
        elif error_code == "INVALID_TABLE":
            table_num = precheck_error.get("table_num")
            return {
                "parsed_order": None,
                "validation_errors": [f"Table {table_num} invalid. Must be 1-20"],
                "error_type": "invalid_table",
                "final_result": None
            }
        elif error_code == "NO_ITEMS":
            return {
                "parsed_order": {"table_num": precheck_error.get("table_num")},
                "validation_errors": ["No items in order"],
                "error_type": "no_items",
                "final_result": None
            }
    
    # LLM parsing
    prompt = detect_prompt.format(raw_text=state["raw_text"])
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        # Clean JSON response
        content = response.content.strip()
        
        # Remove markdown
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    content = part[4:].strip()
                    break
                elif part and part[0] == "{":
                    content = part
                    break
        
        # Extract JSON
        if not content.startswith("{"):
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                content = content[start:end]
        
        if not content:
            raise ValueError("Empty LLM response")
        
        parsed = json.loads(content)
        
        # Handle LLM error responses
        if "error" in parsed:
            error_code = parsed["error"]
            print(f"❌ LLM ERROR: {error_code}")
            
            if error_code == "NO_TABLE_FOUND":
                return {
                    "parsed_order": None,
                    "validation_errors": ["Table number is missing. Use 'table [number]'"],
                    "error_type": "missing_table",
                    "final_result": None
                }
            elif error_code == "NO_QUANTITY_FOUND":
                return {
                    "parsed_order": {"table_num": parsed.get("table_num")},
                    "validation_errors": ["Quantity is missing for items"],
                    "error_type": "missing_quantity",
                    "final_result": None
                }
            elif error_code == "INVALID_TABLE":
                return {
                    "parsed_order": None,
                    "validation_errors": [parsed.get("reason", "Invalid table number")],
                    "error_type": "invalid_table",
                    "final_result": None
                }
            elif error_code == "INVALID_QUANTITY":
                return {
                    "parsed_order": {"table_num": parsed.get("table_num")},
                    "validation_errors": ["Quantity must be positive integer"],
                    "error_type": "missing_quantity",
                    "final_result": None
                }
        
        # Validate items have quantities
        items = parsed.get("items", [])
        if not items:
            return {
                "parsed_order": {"table_num": parsed.get("table_num")},
                "validation_errors": ["No items in order"],
                "error_type": "no_items",
                "final_result": None
            }
        
        for item in items:
            qty = item.get("qty", 0)
            if not isinstance(qty, int) or qty < 1:
                print(f"❌ DETECT: Invalid quantity {qty}")
                return {
                    "parsed_order": {"table_num": parsed.get("table_num")},
                    "validation_errors": ["Quantity missing or invalid"],
                    "error_type": "missing_quantity",
                    "final_result": None
                }
        
        # Apply correct prices
        items, calculated_total = apply_restaurant_prices(items)
        parsed["items"] = items
        parsed["calculated_total"] = calculated_total
        
        # Use calculated total if not provided
        if not parsed.get("total_amount") or parsed.get("total_amount") == 0:
            parsed["total_amount"] = calculated_total
        
        print(f"✅ DETECTED: table={parsed.get('table_num')}, items={len(items)}, total=₹{calculated_total}")
        return {
            "parsed_order": parsed,
            "attempt": 1,
            "error_type": None
        }
        
    except Exception as e:
        print(f"❌ PARSE FAILED: {e}")
        return {
            "parsed_order": None,
            "validation_errors": ["Cannot parse order format"],
            "error_type": "parse_error",
            "final_result": None
        }

def validate_order(state: CleaningState) -> CleaningState:
    """STEP 2: VERIFY - Validate against business rules"""
    parsed_order = state.get("parsed_order")
    
    print(f"\n✅ VERIFY: {parsed_order}")
    
    if not parsed_order:
        return {
            "validation_errors": state.get("validation_errors", ["No order to validate"]),
            "final_result": None
        }
    
    errors = []
    
    # Rule 1: Table validation
    table_num = parsed_order.get("table_num")
    if not table_num:
        return {
            "validation_errors": ["Table number missing"],
            "error_type": "missing_table",
            "final_result": None
        }
    
    if not isinstance(table_num, int) or not (1 <= table_num <= 20):
        errors.append(f"Table must be 1-20, got {table_num}")
        return {
            "validation_errors": errors,
            "error_type": "invalid_table",
            "final_result": None
        }
    
    # Rule 2: Items validation
    items = parsed_order.get("items", [])
    if not items:
        return {
            "validation_errors": ["No items in order"],
            "error_type": "no_items",
            "final_result": None
        }
    
    # Rule 3: Quantity validation
    for idx, item in enumerate(items):
        qty = item.get("qty")
        if qty is None or not isinstance(qty, int) or qty < 1:
            return {
                "validation_errors": [f"Invalid quantity for item {idx+1}"],
                "error_type": "missing_quantity",
                "final_result": None
            }
    
    # Rule 4: Price correction & total calculation
    items, correct_total = apply_restaurant_prices(items)
    parsed_order["items"] = items
    parsed_order["calculated_total"] = correct_total
    
    # Rule 5: Total verification (auto-repair if mismatch)
    given_total = parsed_order.get("total_amount", 0)
    if given_total > 0 and abs(given_total - correct_total) > 5:
        print(f"⚠️ TOTAL MISMATCH: given=₹{given_total}, correct=₹{correct_total}")
        errors.append(f"Total mismatch: given ₹{given_total}, should be ₹{correct_total}")
        # This is repairable - continue to repair step
    
    if errors and "Total mismatch" in errors[0]:
        return {
            "validation_errors": errors,
            "parsed_order": parsed_order,
            "error_type": "validation_error"  # Repairable
        }
    
    if errors:
        print(f"❌ VALIDATION FAILED: {errors}")
        return {
            "validation_errors": errors,
            "final_result": None
        }
    
    # Pydantic validation
    try:
        order = CleanOrder(**parsed_order)
        print("✅ ALL VERIFICATIONS PASSED")
        return {
            "validation_errors": [],
            "final_result": order.model_dump(),
            "error_type": None
        }
    except ValidationError as e:
        validation_errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        print(f"❌ PYDANTIC FAILED: {validation_errors}")
        return {
            "validation_errors": validation_errors,
            "error_type": "validation_error"
        }

def reflect_and_repair(state: CleaningState) -> CleaningState:
    """STEP 3: REPAIR - Fix repairable errors"""
    attempt = state.get("attempt", 0)
    print(f"\n🔧 REPAIR (attempt {attempt}): {state.get('validation_errors')}")
    
    if attempt >= 2:
        print("❌ Max repair attempts")
        return {
            "final_result": None,
            "validation_errors": state.get("validation_errors", []),
            "error_type": "max_attempts"
        }
    
    parsed_order = state.get("parsed_order", {})
    errors = state.get("validation_errors", [])
    
    # Only repair total mismatches, not missing data
    if any("mismatch" in str(e).lower() or "incorrect" in str(e).lower() for e in errors):
        # Auto-repair: Force correct prices and total
        items = parsed_order.get("items", [])
        items, correct_total = apply_restaurant_prices(items)
        parsed_order["items"] = items
        parsed_order["total_amount"] = correct_total
        parsed_order["calculated_total"] = correct_total
        
        print(f"✅ REPAIRED: total=₹{correct_total}")
        return {
            "parsed_order": parsed_order,
            "attempt": attempt + 1,
            "validation_errors": [],
            "error_type": None
        }
    
    # Cannot repair other errors
    return {
        "final_result": None,
        "validation_errors": errors,
        "error_type": "repair_failed"
    }

def should_continue(state: CleaningState) -> str:
    """Router: Decide next step"""
    print(f"\n🔀 ROUTE: attempt={state.get('attempt', 0)}, error_type={state.get('error_type')}")
    
    if state.get("final_result"):
        print("✅ → END (success)")
        return END
    
    # Critical errors - cannot repair
    critical_errors = [
        "missing_table", "missing_quantity", "invalid_table",
        "no_items", "parse_error", "max_attempts", "repair_failed"
    ]
    
    if state.get("error_type") in critical_errors:
        print(f"🚫 → END (critical: {state.get('error_type')})")
        return END
    
    if state.get("attempt", 0) >= 2:
        print("🚫 → END (max attempts)")
        return END
    
    # Repairable validation errors
    if state.get("validation_errors"):
        print("🔄 → repair")
        return "repair"
    
    print("🚫 → END (default)")
    return END

# ✅ BUILD GRAPH
workflow = StateGraph(CleaningState)
workflow.add_node("parse", parse_raw)
workflow.add_node("validate", validate_order)
workflow.add_node("repair", reflect_and_repair)

workflow.set_entry_point("parse")
workflow.add_edge("parse", "validate")
workflow.add_conditional_edges(
    "validate",
    should_continue,
    {
        "repair": "repair",
        END: END
    }
)
workflow.add_edge("repair", "validate")

cleaner = workflow.compile()

def merge_orders(existing_order: dict, new_items: list) -> tuple[list, float]:
    """Merge new items with existing unpaid order"""
    print(f"\n🔄 MERGE: Adding {len(new_items)} items to existing order")
    
    # Combine items
    merged_items = existing_order.get("items", []).copy()
    
    for new_item in new_items:
        # Check if item already exists
        found = False
        for existing_item in merged_items:
            if existing_item["name"].lower() == new_item["name"].lower():
                # Merge quantities
                existing_item["qty"] += new_item["qty"]
                found = True
                print(f"  ➕ {new_item['name']}: {existing_item['qty']-new_item['qty']} + {new_item['qty']} = {existing_item['qty']}")
                break
        
        if not found:
            merged_items.append(new_item)
            print(f"  🆕 {new_item['name']}: qty={new_item['qty']}")
    
    # Recalculate total
    _, new_total = apply_restaurant_prices(merged_items)
    
    return merged_items, new_total

async def clean_order(raw_text: str, existing_order_check=None) -> Dict[str, Any]:
    """
    Main entry point with order merging logic
    
    Args:
        raw_text: WhatsApp message
        existing_order_check: Function(table_num) -> dict | None
                             Returns existing unpaid order for table if exists
    """
    print(f"\n{'='*60}\n🚀 PROCESSING: '{raw_text}'\n{'='*60}")
    
    result = await cleaner.ainvoke({
        "raw_text": raw_text,
        "attempt": 0,
        "messages": [],
        "parsed_order": None,
        "validation_errors": [],
        "final_result": None,
        "error_type": None,
        "existing_order": None
    })
    
    if result.get("final_result"):
        order = result["final_result"]
        table_num = order.get("table_num")
        
        # Check for existing unpaid order
        existing_order = None
        if existing_order_check:
            existing_order = existing_order_check(table_num)
        
        if existing_order and existing_order.get("status") != "paid":
            # MERGE orders
            merged_items, new_total = merge_orders(existing_order, order["items"])
            
            print(f"\n{'='*60}\n✅ MERGED ORDER\n{'='*60}")
            return {
                "success": True,
                "merged": True,
                "order": {
                    **order,
                    "items": merged_items,
                    "total_amount": new_total
                },
                "previous_total": existing_order.get("total_amount", 0),
                "new_total": new_total,
                "attempts": result.get("attempt", 1),
                "message": f"Added to existing order. New total: ₹{new_total}"
            }
        
        # NEW order
        print(f"\n{'='*60}\n✅ SUCCESS\n{'='*60}")
        return {
            "success": True,
            "merged": False,
            "order": order,
            "attempts": result.get("attempt", 1),
            "message": "Order processed successfully"
        }
    
    # FAILURE - Generate user-friendly error
    error_type = result.get("error_type")
    errors = result.get("validation_errors", [])
    error_msg = errors[0] if errors else "Unknown error"
    
    # WhatsApp error messages
    error_messages = {
        "missing_table": "❌ Table number is missing!\n\n📝 Correct format:\ntable [number] [quantity] [item]\n\n✅ Examples:\n• table 5 3 idly\n• table 10 4 vada 2 coffee",
        
        "invalid_table": f"❌ {error_msg}\n\n📝 Table numbers must be 1-20\n\n✅ Example: table 5 3 idly",
        
        "missing_quantity": "❌ Quantity is missing!\n\n📝 Correct format:\ntable [number] [quantity] [item]\n\n✅ Examples:\n• table 5 3 idly\n• table 8 2 dosa",
        
        "no_items": "❌ No items in order!\n\n📝 Add items with quantity:\ntable [number] [quantity] [item]\n\n✅ Example: table 5 3 idly",
        
        "parse_error": "❌ Cannot understand order format!\n\n📝 Use this format:\ntable [number] [quantity] [item]\n\n✅ Example: table 5 3 idly total 45"
    }
    
    whatsapp_msg = error_messages.get(error_type, f"❌ Order error: {error_msg}")
    
    print(f"\n{'='*60}\n❌ FAILED: {error_msg}\n{'='*60}")
    return {
        "success": False,
        "error": error_msg,
        "error_type": error_type,
        "whatsapp_message": whatsapp_msg,
        "suggestion": "Use format: table [number] [quantity] [item]"
    }