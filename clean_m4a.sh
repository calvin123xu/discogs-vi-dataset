#!/bin/bash
# 用法: bash fix_dashed_m4a_safe.sh /path/to/music_dir /path/to/dashed_backup_dir

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 /path/to/music_dir /path/to/dashed_backup_dir"
    exit 1
fi

MUSIC_DIR="$1"
BACKUP_DIR="$2"

mkdir -p "$BACKUP_DIR"

LOG_FILE="$MUSIC_DIR/convert_dashed_m4a.log"
echo "Conversion started at $(date)" > "$LOG_FILE"

# 遍历所有 m4a 文件
find "$MUSIC_DIR" -type f -name "*.m4a" | while IFS= read -r FILE; do
    # 检查是否 dashed
    MAJOR_BRAND=$(ffprobe -v error -show_entries format_tags=major_brand \
                  -of default=noprint_wrappers=1:nokey=1 "$FILE")

    if [ "$MAJOR_BRAND" = "dash" ]; then
        echo "Dashed file detected: $FILE" | tee -a "$LOG_FILE"

        # 生成标准 m4a 临时文件
        TMP_FILE="${FILE}.tmp.m4a"
        ffmpeg -y -i "$FILE" -c copy "$TMP_FILE" >> "$LOG_FILE" 2>&1

        # 移动原 dashed 文件到备份目录，保持原目录结构
        REL_PATH="${FILE#$MUSIC_DIR/}"
        DEST="$BACKUP_DIR/$REL_PATH"
        mkdir -p "$(dirname "$DEST")"
        mv "$FILE" "$DEST"

        # 将临时文件覆盖原文件名
        mv "$TMP_FILE" "$FILE"

        echo "Converted and saved: $FILE" | tee -a "$LOG_FILE"
    else
        echo "Normal file, skipped: $FILE" >> "$LOG_FILE"
    fi
done

echo "Conversion finished at $(date)" >> "$LOG_FILE"

