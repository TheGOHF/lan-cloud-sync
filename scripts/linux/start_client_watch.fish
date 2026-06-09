#!/usr/bin/env fish

set ROOT_DIR (realpath (dirname (status filename))/../..)
set PYTHON_EXE $ROOT_DIR/client/venv/bin/python3
set LOG_DIR $ROOT_DIR/logs
set LOG_FILE $LOG_DIR/client-watch.log

set DEVICE_ID ""
if set -q argv[1]
    set DEVICE_ID $argv[1]
end

mkdir -p $LOG_DIR

if not $PYTHON_EXE --version >/dev/null 2>> $LOG_FILE
    echo "Python не найден: $PYTHON_EXE"
    exit 1
end

cd $ROOT_DIR/client; or exit 1
if test -z $DEVICE_ID
    $PYTHON_EXE -m app.cli.main watch >> $LOG_FILE 2>&1
else
    $PYTHON_EXE -m app.cli.main watch --device-id $DEVICE_ID >> $LOG_FILE 2>&1
end
