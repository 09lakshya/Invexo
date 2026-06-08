#!/bin/bash
# Invexo Oracle Cloud Deployment Script
# Run this script with: sudo bash deploy_oracle.sh

echo "Starting Invexo Oracle Cloud Setup..."

# 1. Update system and install dependencies
echo "Installing Nginx, Python, and Certbot..."
apt-get update
apt-get install -y python3-pip python3-venv nginx certbot python3-certbot-nginx git ufw

# 2. Configure Firewall (Oracle requires this to open ports)
echo "Configuring Firewall..."
ufw allow 'Nginx Full'
ufw allow 22/tcp
# Oracle also has iptables rules by default that block ports, we need to flush or insert them
iptables -I INPUT -p tcp --dport 80 -j ACCEPT
iptables -I INPUT -p tcp --dport 443 -j ACCEPT
netfilter-persistent save

# 3. Setup Python Virtual Environment
echo "Setting up Python Environment..."
cd /home/ubuntu/Invexo/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Setup Systemd Service
echo "Setting up Systemd Service..."
cp /home/ubuntu/Invexo/backend/scripts/invexo.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable invexo
systemctl start invexo

# 5. Setup Nginx
echo "Setting up Nginx Reverse Proxy..."
cp /home/ubuntu/Invexo/backend/scripts/invexo_nginx.conf /etc/nginx/sites-available/invexo
ln -sf /etc/nginx/sites-available/invexo /etc/nginx/sites-enabled/
# Remove default nginx config
rm -f /etc/nginx/sites-enabled/default

# Restart Nginx
systemctl restart nginx

echo "================================================="
echo "Setup Complete!"
echo "Your API is now running on localhost:8000 internally."
echo "Nginx is routing internet traffic to it."
echo "================================================="
echo "To secure your domain with SSL, run:"
echo "sudo certbot --nginx -d YOUR_DOMAIN_NAME"
