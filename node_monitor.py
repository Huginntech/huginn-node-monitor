import json
import requests
import time
import threading

# Read the config file
with open("config.json") as f:
    config = json.load(f)

TELEGRAM_BOT_TOKEN = config["telegram"]["bot_token"]
TELEGRAM_CHAT_ID = config["telegram"]["chat_id"]
NODES = config["nodes"]

# Store the last block heights for each node
last_block_heights = {}

# The last time a red alert was sent (epoch)
last_alert_time = 0
alert_interval = 1800  # 30 minutes

def get_block_height(rpc_url):
    try:
        response = requests.get(f"{rpc_url}/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return int(data["result"]["sync_info"]["latest_block_height"])
    except Exception:
        return None

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=data)

def categorize_nodes(nodes):
    # Group nodes by the first word (e.g., Cosmos, Celestia, etc.)
    categories = {}
    for node in nodes:
        key = node["name"].split()[0]
        categories.setdefault(key, []).append(node)
    # Sort each category alphabetically
    return {k: sorted(v, key=lambda x: x["name"]) for k, v in sorted(categories.items())}

def generate_status_report():
    # Generate a full status report for all nodes
    categorized_nodes = categorize_nodes(NODES)
    message = "*📡 Node Status Report 📡*\n\n"
    for category, nodes in categorized_nodes.items():
        message += f"*🔹 {category} Nodes:*\n"
        for node in nodes:
            rpc_url = node["rpc"]
            node_name = node["name"]
            block_height = get_block_height(rpc_url)
            if block_height is None:
                message += f"🔴 *{node_name}* - *RPC Unreachable!*\n"
            else:
                if node_name in last_block_heights:
                    if last_block_heights[node_name] == block_height:
                        message += f"🔴 *{node_name}* - *Block Not Updating!* (Height: {block_height})\n"
                    else:
                        message += f"🟢 *{node_name}* - OK (Height: {block_height})\n"
                else:
                    message += f"🟢 *{node_name}* - First Check (Height: {block_height})\n"
            last_block_heights[node_name] = block_height
        message += "\n"
    return message

def generate_red_report():
    # Generate a report only for nodes with issues
    categorized_nodes = categorize_nodes(NODES)
    message = "*📡 Red Alert Report 📡*\n\n"
    alert_found = False
    for category, nodes in categorized_nodes.items():
        red_lines = ""
        for node in nodes:
            rpc_url = node["rpc"]
            node_name = node["name"]
            block_height = get_block_height(rpc_url)
            if block_height is None:
                red_lines += f"🔴 *{node_name}* - *RPC Unreachable!*\n"
                alert_found = True
            else:
                if node_name in last_block_heights:
                    if last_block_heights[node_name] == block_height:
                        red_lines += f"🔴 *{node_name}* - *Block Not Updating!* (Height: {block_height})\n"
                        alert_found = True
            last_block_heights[node_name] = block_height
        if red_lines:
            message += f"*🔹 {category} Nodes:*\n" + red_lines + "\n"
    return message if alert_found else ""

def monitor_nodes():
    global last_alert_time
    while True:
        red_report = generate_red_report()
        if red_report:
            current_time = time.time()
            if current_time - last_alert_time >= alert_interval:
                send_telegram_message(TELEGRAM_CHAT_ID, red_report)
                last_alert_time = current_time
        time.sleep(600)  # every 10 min

def handle_telegram_commands():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    last_update_id = None
    while True:
        params = {}
        if last_update_id:
            params["offset"] = last_update_id + 1
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            for update in data.get("result", []):
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    if text == "/status":
                        full_report = generate_status_report()
                        send_telegram_message(chat_id, full_report)
                    last_update_id = update["update_id"]
        time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=monitor_nodes).start()
    threading.Thread(target=handle_telegram_commands).start()
