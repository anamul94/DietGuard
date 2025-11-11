#!/bin/bash

# Test and reload Nginx
nginx -t && systemctl reload nginx