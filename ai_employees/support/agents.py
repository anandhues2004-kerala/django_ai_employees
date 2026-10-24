
#AGENT ENGINE
from support.models import Conversation,Message,AgentLog
from.gemini_client import Anthropic
from django.conf import settings
from.tools import get_order_details,get_refund_history,check_delivery_status
# initialize Antropic Client
client=Anthropic(api_key=settings.GEMINI_API_KEY)
# model 
antropic_model=settings.GEMINI_MODEL

#SUPPORT SYSTEM PROMPT--> Vikram job description

SUPPORT_SYSTEM_PROMPT="""
You are Vikram,a customer support agent at MyG AC.
You help Customers with issues realated to their AC order

Your resposnsibilities:
-Always use your tools to gather facts before responding
-Check order details when customer mentions their order
-check refind history before making any refund decisions
-be empathetic but honest

Your personality
-Friend and profesional
-patient even when customer is angry
-clear and concise in your replies
Important rules:
-Always check order details order before responding
-Never approve or deny a refund yourself
-If refund decisions is need-tell customer you are checking with your team
"""

MANAGER_SYSTEM_PROMPT = """
You are Vishnu, a senior support manager at CoolBreeze AC.
A support agent has escalated a customer case to you for a refund decision.

Your responsibilities:
- Carefully review the case summary provided by the support agent.
- Check the customer's order details and refund history using available tools.
- Verify whether the refund request follows company policy.
- Make a fair and final decision based on verified facts.
- Provide a specific reason for your decision.

Your decision options:
- APPROVE_REFUND: Approve the refund if the case is genuine and meets company policy.
- DENY_REFUND: Deny the refund if the request clearly violates company policy.
- ESCALATE_TO_RISK: Escalate the case if there is credible evidence of possible fraud or suspicious activity.

Important rules:
- Always gather relevant facts before making a decision.
- Never invent order details, refund history, or company policies.
- Do not approve or deny a refund based only on the customer's emotions.
- Consider previous refunds and suspicious patterns, but do not treat refund history alone as proof of fraud.
- If essential information is missing, request the missing information instead of guessing.
- Escalate uncertain fraud cases to the risk team.
- Give a clear, specific reason for every decision.
- Be fair, firm, concise, and professional.

Response format:
Decision: [APPROVE_REFUND / DENY_REFUND / ESCALATE_TO_RISK]
Reason: [Specific reason based on verified facts]
Evidence: [Relevant order details and refund history]
"""

#SUPPORT TOOLS-->Tools schemas ,that ai agent will read
SUPPORT_TOOLS=[
    
{
    "name": "get_order_details",
    "description": "Fetch complete order details, including status, carrier, tracking number, and days since the order was placed. Use this when a customer mentions their order or complains about delivery.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "integer",
                "description": "The order ID to look up."
            }
        },
        "required": ["order_id"]
    }
},

{
    "name": "get_refund_history",
    "description": "Fetch the complete refund history for a user, including order ID, product name, refund reason, refund status, and request date. Use this when a customer asks about previous refunds or wants to check their refund history.",
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "The user ID whose refund history needs to be retrieved."
            }
        },
        "required": ["user_id"]
    }
},

{
    "name": "check_delivery_status",
    "description": "Check the latest available delivery tracking information, including delivery status, last known location, last update, estimated delivery date, and delay reason. Use this when a customer asks where their package is or reports a delivery delay.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tracking_number": {
                "type": "string",
                "description": "The tracking number associated with the shipment."
            },
            "carrier": {
                "type": "string",
                "description": "The delivery company responsible for shipping the order, such as Delhivery or Blue Dart."
            }
        },
        "required": ["tracking_number", "carrier"]
    }
},
   {
        "name": "escalate_to_manager",
        "description": "Escalate the case to manager for refund decision. Always include customer's user_id in the case summary so manager can assess fraud risk accurately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_summary": {
                    "type": "string",
                    "description": "Complete case summary. Must include: customer user_id, order details, refund history and complaint. Format: Start with 'Customer User ID: X' on the first line."
                }
            },
            "required": ["case_summary"]
        }
    }

]


#execute_tool-->Bridge between Gemini and python functions(tools)

def execute_tool(tool_name,tool_input):
    if tool_name=="get_order_details":
        return get_order_details(tool_input["order_id"])
    if tool_name=="get_refund_history":
        return get_refund_history(tool_input["user_id"])
    if tool_name=="check_delivery_status":
        return check_delivery_status(tool_input["tracking_number"],tool_input["carrier"])
    if tool_name =="escalate_to_manager":
        case_summary=tool_input["case_summary"]
        decision=run_manager_agent(case_summary)
        return decision



    
def run_support_agent(user_message, conversation_id, order_id, user_id):
    conv = Conversation.objects.get(id=conversation_id)

    # Get previous messages
    conversation_messages = []

    for msg in conv.messages.order_by("created_at"):
        conversation_messages.append({
            "role": msg.role,
            "content": msg.content,
        })

    # Add the current message
    if not conversation_messages :
        conversation_messages.append({
            "role": "user",
            "content": user_message,
        })

    # Keep asking the AI until it gives a final answer
    while True:
        response = client.messages.create(
            model=antropic_model,
            max_tokens=1024,
            system=SUPPORT_SYSTEM_PROMPT + (
                f"\nOrder ID: {order_id}, User ID: {user_id}"
            ),
            tools=SUPPORT_TOOLS,
            messages=conversation_messages,
        )

        # Check whether the AI wants to use a tool
        if response.stop_reason == "tool_use":

            # Keep the original tool call
            conversation_messages.append({
                "role": "assistant",
                "content": list(response.content),
            })

            tool_results = []

            # Run the requested tool
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)

                    #store data

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            # Send tool results back to the AI
            conversation_messages.append({
                "role": "user",
                "content": tool_results,
            })

        else:
            return response.content[0].text


#create the manager agent

def run_manager_agent(case_summary):
    manager_messages=[
        {'role':"user","content":case_summary}#user is task give in this case user is our agent vikram

    ]
    while True:
        response=client.messages.create(
            model=antropic_model,
            max_tokens=1024,
            system=MANAGER_SYSTEM_PROMPT,
            messages=manager_messages,
             tools=SUPPORT_TOOLS

        )
        if response.stop_reason=='tool_use':
            tool_result=[]
            for i in response.content:
                if i.type=='tool_use':
                    result=execute_tool(i.name,i.input)

                    tool_result.append({
                        "type": "tool_result",
                        "tool_use_id": i.id,
                        "content": str(result),

                    })
            manager_messages.append({
                "role":"assistant",
                "content":response.content
            })  

            manager_messages.append({
                "role":"user",
                "content":tool_result
            })   
        else:
            return response.content[0].text
               

        