import qrcode, os

output_dir = "qr_codes"
os.makedirs(output_dir, exist_ok=True)


# CHANGE this to your IP address from ipconfig
server_ip = "172.17.49.199"


for roll in range(1, 641):
    qr_text = f"http://{server_ip}:5000/mark?roll={roll}"
    img = qrcode.make(qr_text)
    img.save(os.path.join(output_dir, f"roll_{roll}.png"))

print("✅ QR codes created with your server IP!")
