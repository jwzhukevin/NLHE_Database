#!/bin/bash

export FLASK_APP=wsgi.py

MEMBERS_DIR="app/static/members"
for dir in "$MEMBERS_DIR"/*/ ; do
    [ -d "$dir" ] || continue
    info_file="${dir}info.json"
    photo_file="${dir}photo.jpg"
    if [ -f "$info_file" ]; then
        flask import-member --info "$info_file" --photo "$photo_file"
        echo "已导入成员：$dir"
    else
        echo "未找到 $info_file，跳过 $dir"
    fi
done 