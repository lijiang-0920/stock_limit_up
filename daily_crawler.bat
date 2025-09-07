@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 创建日志目录
if not exist logs mkdir logs

:: 设置日志文件
set LOGFILE=logs\crawler_%date:~0,4%%date:~5,2%%date:~8,2%.log

:: 记录开始时间
echo. >> %LOGFILE%
echo ============================================= >> %LOGFILE%
echo %date% %time% - 涨停透视爬虫任务开始 >> %LOGFILE%
echo ============================================= >> %LOGFILE%

:: 进入工作目录
cd /d "D:\Microsoft VS Code\ztts_crawler"

:: 检查是否为交易日（周一到周五）
for /f %%i in ('powershell -command "(Get-Date).DayOfWeek"') do set DAYOFWEEK=%%i
if "%DAYOFWEEK%"=="Saturday" (
    echo %date% %time% - 今天是周六，跳过爬虫任务 >> %LOGFILE%
    goto :end
)
if "%DAYOFWEEK%"=="Sunday" (
    echo %date% %time% - 今天是周日，跳过爬虫任务 >> %LOGFILE%
    goto :end
)

:: 检查时间（只在15:30-18:00之间运行）
for /f "tokens=1-2 delims=:" %%a in ('time /t') do (
    set HOUR=%%a
    set MINUTE=%%b
)
set /a CURRENT_TIME=%HOUR%*60+%MINUTE%
set /a START_TIME=15*60+30
set /a END_TIME=18*60

if %CURRENT_TIME% LSS %START_TIME% (
    echo %date% %time% - 当前时间过早，跳过爬虫任务 >> %LOGFILE%
    goto :end
)
if %CURRENT_TIME% GTR %END_TIME% (
    echo %date% %time% - 当前时间过晚，跳过爬虫任务 >> %LOGFILE%
    goto :end
)

echo %date% %time% - 开始执行爬虫... >> %LOGFILE%

:: 先拉取最新代码
echo %date% %time% - 拉取最新代码... >> %LOGFILE%
"D:\Git\cmd\git.exe" pull >> %LOGFILE% 2>&1

:: 运行爬虫，最多重试3次
set RETRY_COUNT=0
set MAX_RETRIES=3

:retry_crawler
set /a RETRY_COUNT+=1
echo %date% %time% - 第 %RETRY_COUNT% 次尝试运行爬虫... >> %LOGFILE%

python ztts_crawler_simple.py >> %LOGFILE% 2>&1

:: 检查爬虫是否成功（检查是否生成了数据文件）
set SUCCESS=0
for /f %%i in ('dir /b dzh_ztts\*\*.json 2^>nul ^| find /c /v ""') do set FILE_COUNT=%%i
if %FILE_COUNT% GTR 0 (
    echo %date% %time% - 爬虫执行成功，发现 %FILE_COUNT% 个数据文件 >> %LOGFILE%
    set SUCCESS=1
) else (
    echo %date% %time% - 爬虫执行失败，未发现数据文件 >> %LOGFILE%
)

:: 如果失败且未达到最大重试次数，等待后重试
if %SUCCESS%==0 (
    if %RETRY_COUNT% LSS %MAX_RETRIES% (
        echo %date% %time% - 等待5分钟后重试... >> %LOGFILE%
        timeout /t 300 /nobreak >nul
        goto :retry_crawler
    ) else (
        echo %date% %time% - 爬虫重试次数已达上限，任务失败 >> %LOGFILE%
        goto :end
    )
)

:: 爬虫成功后，尝试推送到GitHub
echo %date% %time% - 开始推送到GitHub... >> %LOGFILE%

set PUSH_RETRY_COUNT=0
set MAX_PUSH_RETRIES=5

:retry_push
set /a PUSH_RETRY_COUNT+=1
echo %date% %time% - 第 %PUSH_RETRY_COUNT% 次尝试推送到GitHub... >> %LOGFILE%

:: 检查是否有需要推送的更改
"D:\Git\cmd\git.exe" add . >> %LOGFILE% 2>&1
"D:\Git\cmd\git.exe" diff --cached --quiet
if %ERRORLEVEL%==0 (
    echo %date% %time% - 没有新的更改需要推送 >> %LOGFILE%
    goto :push_success
)

:: 提交更改
"D:\Git\cmd\git.exe" commit -m "Auto update 涨停透视数据 %date%" >> %LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %date% %time% - Git提交失败 >> %LOGFILE%
    goto :push_failed
)

:: 推送到GitHub
"D:\Git\cmd\git.exe" push >> %LOGFILE% 2>&1
if %ERRORLEVEL%==0 (
    echo %date% %time% - GitHub推送成功 >> %LOGFILE%
    goto :push_success
) else (
    echo %date% %time% - GitHub推送失败 >> %LOGFILE%
    goto :push_failed
)

:push_failed
if %PUSH_RETRY_COUNT% LSS %MAX_PUSH_RETRIES% (
    echo %date% %time% - 等待2分钟后重试推送... >> %LOGFILE%
    timeout /t 120 /nobreak >nul
    goto :retry_push
) else (
    echo %date% %time% - 推送重试次数已达上限，推送失败 >> %LOGFILE%
    goto :end
)

:push_success
echo %date% %time% - 所有任务执行成功 >> %LOGFILE%

:end
echo %date% %time% - 涨停透视爬虫任务结束 >> %LOGFILE%
echo ============================================= >> %LOGFILE%
