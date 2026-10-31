
#AGENT ENGINE
from support.models import Conversation,Message,AgentLog
from.gemini_client import Anthropic
from django.conf import settings
from.tools import get_order_details,get_refund_history,check_delivery_status, get_customer_risk_profile
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

RISK_SYSTEM_PROMPT="""
You are a fraud risk analyst at CoolBreeze AC.
A support manager has sent you a customer profile for risk assessment.

Your job:
- Analyse the customer's order and refund patterns
- Identify suspicious behaviour
- Return a clear risk verdict

Risk levels:
- LOW — genuine customer, normal behaviour
- MEDIUM — some suspicious signals, proceed with caution
- HIGH — clear fraud pattern, recommend denial

Your response format:
- Risk Level: LOW / MEDIUM / HIGH
- Key Signals: what you found suspicious or genuine
- Recommendation: what manager should do

Important:
- Be objective — base verdict on data only
- One bad refund does not make someone fraudulent
- Look for patterns — not isolated incidents

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

MANAGER_TOOLS = [
    {
        "name": "assess_fraud_risk",
        "description": "Consult the risk agent to assess fraud risk for a customer. Use this when refund request looks suspicious or customer has multiple refund requests. Pass the user_id to get a risk verdict.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The user ID to assess fraud risk for"
                }
            },
            "required": ["user_id"]
        }
    }
]

RISK_TOOLS = [
    {
        "name": "get_customer_risk_profile",
        "description": "Get complete risk profile for a customer including order history, refund patterns and ratio. Use this to assess fraud risk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The user ID to assess risk for"
                }
            },
            "required": ["user_id"]
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
    if tool_name=='assess_fraud_risk':
        user_id=tool_input['user_id']
        print("Consulating risk agent for user==>",user_id)
        verdict=run_risk_agent(user_id)
        print("risk verdict==>",verdict)
        return verdict
    if tool_name==' get_customer_risk_profile':
        return get_customer_risk_profile(tool_input['user_id'])

        
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
            tools=MANAGER_TOOLS,
            messages=manager_messages,
             

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

def run_risk_agent(user_id):
    risk_messages=[
        {"role":"user","content":f"please assess the fraud risk for user ID {user_id}.User your tool to get their profile"}
    ]  
    while True:
        response=client.messages.create(
            model=antropic_model,
            max_tokens=1024,
            system=RISK_SYSTEM_PROMPT,
            tools=RISK_TOOLS,
            messages=risk_messages

        ) 

        print("risk stop_reason===>",response.stop_reason)  
        if response.stop_reason=='tool_use': 
            tool_result=[]
            for block in response.content:
                if block.type == "tool_use":
                    print("risk tool call ==>",block.name) #means tool name
                    print("risk tool input ===>",block.input) 
                    result = execute_tool(block.name,block.input)#execute tool take this
                    print('risk tool result==>',result)
                    tool_result.append({
                        "type":"tool_result",
                         "tool_use_id":block.id,
                         "content":str(result)
                })
                risk_messages.append({
                    "role":"assistant",
                     "content":response.content

        })  
                risk_messages.append({
                    "role":"user",
                    "content":tool_result
        }) 
        else:
            return response.content[0].text             

               

        