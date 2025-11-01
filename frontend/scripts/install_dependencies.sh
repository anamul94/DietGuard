#!/bin/bash
apt-get update -y
apt-get install -y nginx
systemctl enable nginx