// 全局状态
let currentMode = null; // 'full' 或 'incremental'
let isDecrypting = false;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('微信数据库解密工具已加载');
});

// 选择解密模式
function selectMode(mode) {
    currentMode = mode;

    // 更新卡片样式
    document.querySelectorAll('.mode-card').forEach(card => {
        card.classList.remove('active');
    });

    const selectedCard = mode === 'full'
        ? document.getElementById('full-decrypt-card')
        : document.getElementById('incremental-decrypt-card');

    selectedCard.classList.add('active');

    // 显示配置表单
    const configForm = document.getElementById('config-form');
    configForm.classList.add('active');

    // 滚动到表单
    configForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    addLog('info', `已选择${mode === 'full' ? '首次解密' : '增量解密'}模式`);
}

// 开始解密
async function startDecryption() {
    if (isDecrypting) {
        return;
    }

    // 验证输入
    const key = document.getElementById('decryption-key').value.trim();
    const dbPath = document.getElementById('db-path').value.trim();
    const accountName = document.getElementById('account-name').value.trim();

    if (!key) {
        alert('请输入解密密钥');
        return;
    }

    if (key.length !== 64) {
        alert('密钥长度必须为64位十六进制字符');
        return;
    }

    if (!/^[0-9a-fA-F]{64}$/.test(key)) {
        alert('密钥必须是有效的十六进制字符串');
        return;
    }

    if (!dbPath) {
        alert('请输入数据库路径');
        return;
    }

    if (!currentMode) {
        alert('请先选择解密模式');
        return;
    }

    // 开始解密
    isDecrypting = true;
    document.getElementById('decrypt-btn').disabled = true;

    // 显示进度区域
    const progressSection = document.getElementById('progress-section');
    progressSection.style.display = 'block';
    progressSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // 隐藏结果区域
    document.getElementById('result-section').style.display = 'none';

    // 清空日志
    clearLog();

    addLog('info', '开始解密任务...');
    addLog('info', `模式: ${currentMode === 'full' ? '首次解密' : '增量解密'}`);
    addLog('info', `密钥: ${key.substring(0, 16)}...${key.substring(48)}`);
    addLog('info', `路径: ${dbPath}`);

    try {
        // 调用后端API
        const response = await fetch('/api/decrypt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                mode: currentMode,
                key: key,
                db_path: dbPath,
                account_name: accountName || null
            })
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            handleSuccess(result);
        } else {
            handleError(result.message || '解密失败');
        }

    } catch (error) {
        console.error('解密错误:', error);
        handleError(`网络错误: ${error.message}`);
    } finally {
        isDecrypting = false;
        document.getElementById('decrypt-btn').disabled = false;
    }
}

// 处理成功
function handleSuccess(result) {
    addLog('success', '解密完成！');

    // 更新进度
    updateProgress(100, result.successful_count, result.total_databases);

    // 显示结果
    document.getElementById('result-section').style.display = 'block';
    document.getElementById('success-result').style.display = 'block';
    document.getElementById('error-result').style.display = 'none';

    const message = `
        成功解密 ${result.successful_count}/${result.total_databases} 个数据库文件<br>
        输出目录: ${result.output_directory}
    `;
    document.getElementById('success-message').innerHTML = message;

    // 添加详细日志
    if (result.processed_files && result.processed_files.length > 0) {
        addLog('success', `已解密的文件:`);
        result.processed_files.slice(0, 10).forEach(file => {
            addLog('info', `  ✓ ${file}`);
        });
        if (result.processed_files.length > 10) {
            addLog('info', `  ... 还有 ${result.processed_files.length - 10} 个文件`);
        }
    }

    // 滚动到结果
    document.getElementById('result-section').scrollIntoView({
        behavior: 'smooth',
        block: 'nearest'
    });
}

// 处理错误
function handleError(errorMessage) {
    addLog('error', `错误: ${errorMessage}`);

    // 显示错误结果
    document.getElementById('result-section').style.display = 'block';
    document.getElementById('success-result').style.display = 'none';
    document.getElementById('error-result').style.display = 'block';

    document.getElementById('error-message').textContent = errorMessage;

    // 滚动到结果
    document.getElementById('result-section').scrollIntoView({
        behavior: 'smooth',
        block: 'nearest'
    });
}

// 更新进度
function updateProgress(percentage, processed, total) {
    document.getElementById('progress-bar-fill').style.width = `${percentage}%`;
    document.getElementById('progress-text').textContent = `${Math.round(percentage)}%`;
    document.getElementById('processed-count').textContent = processed;
    document.getElementById('total-count').textContent = total;

    if (percentage === 100) {
        document.getElementById('progress-status').textContent = '完成';
        document.getElementById('success-count').textContent = processed;
        document.getElementById('failed-count').textContent = total - processed;
    } else {
        document.getElementById('progress-status').textContent = '解密中...';
    }
}

// 添加日志
function addLog(type, message) {
    const logContent = document.getElementById('log-content');
    const timestamp = new Date().toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;

    logContent.appendChild(logEntry);
    logContent.scrollTop = logContent.scrollHeight;
}

// 清空日志
function clearLog() {
    document.getElementById('log-content').innerHTML = '';

    // 重置进度
    updateProgress(0, 0, 0);
    document.getElementById('progress-status').textContent = '准备中...';
    document.getElementById('success-count').textContent = '0';
    document.getElementById('failed-count').textContent = '0';
}

// 打开输出文件夹
function openOutputFolder() {
    addLog('info', '正在打开输出文件夹...');

    // 调用后端API打开文件夹
    fetch('/api/open-folder', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    }).then(response => {
        if (response.ok) {
            addLog('success', '已打开输出文件夹');
        } else {
            addLog('error', '无法打开文件夹');
        }
    }).catch(error => {
        console.error('打开文件夹错误:', error);
        addLog('error', `打开文件夹失败: ${error.message}`);
    });
}

// 重置表单
function resetForm() {
    // 重置表单
    document.getElementById('decryption-key').value = '';
    document.getElementById('db-path').value = '';
    document.getElementById('account-name').value = '';

    // 重置模式选择
    document.querySelectorAll('.mode-card').forEach(card => {
        card.classList.remove('active');
    });
    currentMode = null;

    // 隐藏各个区域
    document.getElementById('config-form').classList.remove('active');
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';

    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });

    addLog('info', '已重置表单');
}

// 显示帮助
function showHelp() {
    const helpMessage = `
微信数据库解密工具使用帮助

1. 获取解密密钥:
   - 使用 WeChatKeyExtractor 工具提取密钥
   - 密钥为64位十六进制字符串

2. 设置数据库路径:
   - 找到微信数据目录，通常在:
     C:\\Users\\你的用户名\\Documents\\WeChat Files\\
   - 选择对应账号下的 db_storage 文件夹

3. 选择解密模式:
   - 首次解密: 解密所有数据库文件
   - 增量解密: 只解密最新的消息数据库

4. 查看解密结果:
   - 解密后的文件保存在 output/databases 目录
   - 每个账号有独立的文件夹

注意事项:
- 请确保微信已关闭
- 解密过程中请勿关闭程序
- 解密后的数据请妥善保管
    `;

    alert(helpMessage);
}

// 显示关于
function showAbout() {
    const aboutMessage = `
微信数据库解密工具 v1.0

基于 WeChatDataAnalysis 项目重构
使用 SQLCipher 4.0 加密机制

技术栈:
- 前端: HTML5, CSS3, JavaScript
- 后端: Python, Flask
- 加密: AES-256-CBC, PBKDF2-SHA512

© 2025 All Rights Reserved
    `;

    alert(aboutMessage);
}

// WebSocket 连接（用于实时进度更新）
function connectWebSocket() {
    const ws = new WebSocket(`ws://${window.location.host}/ws`);

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === 'progress') {
            updateProgress(
                data.percentage,
                data.processed,
                data.total
            );
            addLog('info', data.message);
        } else if (data.type === 'log') {
            addLog(data.level, data.message);
        }
    };

    ws.onerror = function(error) {
        console.error('WebSocket错误:', error);
    };

    ws.onclose = function() {
        console.log('WebSocket连接已关闭');
        // 5秒后尝试重连
        setTimeout(connectWebSocket, 5000);
    };

    return ws;
}

// 页面加载时连接WebSocket
// let websocket = connectWebSocket();
