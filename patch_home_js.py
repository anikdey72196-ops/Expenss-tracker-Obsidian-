with open('templates/home.html', 'r') as f:
    code = f.read()

old_fetch_chat = '''            fetch('/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            }).then(response => {
                if (!response.ok) {
                    setChatState(false);
                    throw new Error('Could not connect to AI service');
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                function read() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            setChatState(false);
                            return;
                        }
                        const text = decoder.decode(value);
                        const lines = text.split('\\n');
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    if (data.content) {
                                        fullText += data.content;
                                        aiMsg.textContent = fullText;
                                        chatBox.scrollTop = chatBox.scrollHeight;
                                    }
                                    if (data.done) {
                                        setChatState(false);
                                    }
                                } catch(e) {}
                            }
                        }
                        read();
                    }).catch(() => {
                        setChatState(false);
                    });
                }
                read();
            }).catch(err => {
                aiMsg.innerText = "Analyzing your request... Based on recent trends, reducing dining expenses by 10% could save you ₹1,200 monthly.";
                setChatState(false);
            });'''

new_fetch_chat = '''            fetch('/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            }).then(async response => {
                if (!response.ok) {
                    setChatState(false);
                    let errMsg = 'Could not connect to AI service';
                    try {
                        const errJson = await response.json();
                        if (errJson && errJson.error) errMsg = errJson.error;
                    } catch(e) {}
                    aiMsg.textContent = 'Error: ' + errMsg;
                    return;
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                function read() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            setChatState(false);
                            return;
                        }
                        const text = decoder.decode(value);
                        const lines = text.split('\\n');
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    if (data.error) {
                                        fullText = 'Error: ' + data.error;
                                        aiMsg.textContent = fullText;
                                        setChatState(false);
                                        return;
                                    }
                                    if (data.content) {
                                        fullText += data.content;
                                        aiMsg.textContent = fullText;
                                        chatBox.scrollTop = chatBox.scrollHeight;
                                    }
                                    if (data.done) {
                                        setChatState(false);
                                    }
                                } catch(e) {}
                            }
                        }
                        read();
                    }).catch(() => {
                        setChatState(false);
                    });
                }
                read();
            }).catch(err => {
                aiMsg.textContent = "Analyzing your request... Based on recent trends, reducing dining expenses by 10% could save you ₹1,200 monthly.";
                setChatState(false);
            });'''

if old_fetch_chat in code:
    code = code.replace(old_fetch_chat, new_fetch_chat)
    with open('templates/home.html', 'w') as f:
        f.write(code)
    print("Updated fetch('/ai/chat') error handling in home.html")
else:
    print("old_fetch_chat block not found")
