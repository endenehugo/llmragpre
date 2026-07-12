(function () {
    var baseUrl = credentialsBaseUrl;
    var $chatlogs = $('.chatlogs');
    var state = {
        currentConversationId: '',
        conversationList: [],
        currentConversationMessages: [],
        currentConversationDocuments: [],
        pendingConversationPromise: null,
        pendingImageUrls: [],
    };

    function apiRequest(options) {
        var deferred = $.Deferred();
        $.ajax($.extend({
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            headers: {},
        }, options)).done(function (response, textStatus, jqXHR) {
            if (response && response.code && response.code !== 'success') {
                deferred.reject({
                    responseJSON: response,
                    status: 200,
                    jqXHR: jqXHR,
                }, textStatus || 'error', response.message || 'Application error');
                return;
            }
            deferred.resolve(response, textStatus, jqXHR);
        }).fail(function (xhr, textStatus, errorThrown) {
            deferred.reject(xhr, textStatus, errorThrown);
        });
        return deferred.promise();
    }

    function setConversationState(hasConversation) {
        $('body').toggleClass('page-has-conversation', hasConversation);
    }

    function showLoading() {
        $('#loadingGif').appendTo($chatlogs).show();
        $('.input').prop('disabled', true);
        $('#sendMessage').prop('disabled', true);
    }

    function hideLoading() {
        $('.input').prop('disabled', false);
        $('#sendMessage').prop('disabled', false);
        $('#loadingGif').hide();
    }

    function scrollToBottom() {
        $chatlogs.stop().animate({ scrollTop: $chatlogs[0].scrollHeight });
    }

    function normalizeMessage(messageText) {
        return String(messageText).replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n');
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function isSafeImageUrl(url) {
        return /^\/conversation\/image\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(url || '');
    }

    function appendTextWithLineBreaks($container, text) {
        var parts = String(text || '').split('\n');
        parts.forEach(function (part, index) {
            if (part) {
                $container.append(document.createTextNode(part));
            }
            if (index < parts.length - 1) {
                $container.append($('<br/>'));
            }
        });
    }

    function renderMessageHtml(text) {
        var normalized = normalizeMessage(text || '');
        var $container = $('<div/>');
        var regex = /!\[([^\]]*)\]\(([^)]+)\)/g;
        var lastIndex = 0;
        var match;

        while ((match = regex.exec(normalized)) !== null) {
            var fullMatch = match[0];
            var alt = match[1] || 'image';
            var url = match[2] || '';
            appendTextWithLineBreaks($container, normalized.slice(lastIndex, match.index));

            if (isSafeImageUrl(url)) {
                $container.append($('<img/>', {
                    src: url,
                    alt: escapeHtml(alt),
                    'class': 'chat-inline-image',
                    loading: 'lazy',
                }));
            } else {
                appendTextWithLineBreaks($container, fullMatch);
            }
            lastIndex = match.index + fullMatch.length;
        }

        appendTextWithLineBreaks($container, normalized.slice(lastIndex));
        return $container.html();
    }

    function composeUserMessage(text, imageUrls) {
        var lines = [];
        (imageUrls || []).forEach(function (url) {
            lines.push('![image](' + url + ')');
        });
        if (text) {
            lines.push(text);
        }
        return lines.join('\n');
    }

    function renderImagePreview() {
        var $container = $('#imagePreviewContainer');
        $container.empty();

        if (!state.pendingImageUrls.length) {
            $container.hide();
            return;
        }

        state.pendingImageUrls.forEach(function (url, index) {
            var $item = $('<div/>', { 'class': 'image-preview-item', 'data-index': index });
            $item.append($('<img/>', { src: url, alt: 'pending image', loading: 'lazy' }));
            $item.append($('<button/>', {
                type: 'button',
                'class': 'image-preview-remove',
                'data-index': index,
                text: '×',
            }));
            $container.append($item);
        });

        $container.css('display', 'flex');
    }

    function renderConversationList() {
        var $container = $('#conversationList');
        $container.empty();

        if (!state.conversationList.length) {
            $container.append($('<div/>', { 'class': 'empty-state', text: '还没有历史会话。' }));
            return;
        }

        state.conversationList.forEach(function (conversation) {
            var $item = $('<button/>', {
                type: 'button',
                'class': 'conversation-item' + (conversation.conversation_id === state.currentConversationId ? ' is-active' : ''),
                'data-id': conversation.conversation_id,
            });
            $item.append($('<p/>', { 'class': 'conversation-item-title', text: conversation.title || '新对话' }));
            $item.append($('<p/>', {
                'class': 'conversation-item-meta',
                text: (conversation.last_message_preview || '暂无消息') + ' · ' + (conversation.updated_at || ''),
            }));
            $container.append($item);
        });
    }

    function renderDocumentList() {
        var $container = $('#documentList');
        $container.empty();

        if (!state.currentConversationDocuments.length) {
            $container.append($('<div/>', { 'class': 'empty-state', text: '当前会话还没有上传文档。' }));
            return;
        }

        state.currentConversationDocuments.forEach(function (documentItem) {
            var $item = $('<div/>', { 'class': 'document-item' });
            var $header = $('<div/>', { 'class': 'document-item-header' });
            $header.append($('<p/>', { 'class': 'document-item-title', text: documentItem.original_name }));
            $header.append($('<button/>', {
                type: 'button',
                'class': 'document-delete',
                'data-id': documentItem.document_id,
                text: '删除',
            }));
            $item.append($header);
            $item.append($('<p/>', {
                'class': 'document-item-meta',
                text: '状态: ' + documentItem.status + ' · 字数: ' + documentItem.char_count,
            }));
            $container.append($item);
        });
    }

    function renderMessages() {
        $('.chatlogs .chat.dynamic-message').remove();
        $('#emptyAssistantMessage').toggle(!state.currentConversationMessages.length);
        state.currentConversationMessages.forEach(function (message) {
            if (message.role === 'user') {
                appendUserMessage(message.content, true);
                return;
            }
            appendAssistantMessage(message.content, true);
        });
        scrollToBottom();
    }

    function appendUserMessage(text, isReplay) {
        var classes = 'chat self dynamic-message';
        $chatlogs.append(
            $('<div/>', { 'class': classes, 'data-replay': isReplay ? '1' : '0' }).append(
                $('<div/>', { 'class': 'user-photo' }).append($('<img src="/static/images/ana.JPG" alt="user avatar" />')),
                $('<div/>', { 'class': 'chat-message', html: renderMessageHtml(text) })
            )
        );
        scrollToBottom();
    }

    function appendAssistantMessage(text, isReplay) {
        $chatlogs.append(
            $('<div/>', { 'class': 'chat friend dynamic-message', 'data-replay': isReplay ? '1' : '0' }).append(
                $('<div/>', { 'class': 'user-photo' }).append($('<img src="/static/images/ana.JPG" alt="assistant avatar" />')),
                $('<div/>', { 'class': 'chat-message', html: renderMessageHtml(text) })
            )
        );
        scrollToBottom();
    }

    function syncConversationSummary(detail) {
        if (!detail) {
            return;
        }
        var existingIndex = -1;
        state.conversationList.forEach(function (item, index) {
            if (item.conversation_id === detail.conversation_id) {
                existingIndex = index;
            }
        });

        var summary = {
            conversation_id: detail.conversation_id,
            title: detail.title,
            mode: detail.mode,
            message_count: detail.message_count,
            last_message_preview: detail.last_message_preview,
            created_at: detail.created_at,
            updated_at: detail.updated_at,
        };

        if (existingIndex >= 0) {
            state.conversationList.splice(existingIndex, 1);
        }
        state.conversationList.unshift(summary);
        renderConversationList();
        updateWorkspaceHeader(detail);
    }

    function updateWorkspaceHeader(detail) {
        $('#currentConversationTitle').text(detail && detail.title ? detail.title : '未选择会话');
        $('#workspaceTitle').text(detail && detail.title ? detail.title : '今天想了解点什么？');
        $('#workspaceSubtitle').text(detail ? '当前会话已持久化，可继续聊天或上传文档。' : '会话、文档和历史记录都会自动持久化。');
    }

    function newRecievedMessage(messageText) {
        var normalizedMessage = normalizeMessage(messageText);
        $('#emptyAssistantMessage').hide();
        appendAssistantMessage(normalizedMessage, false);
    }

    function loadConversationList() {
        return apiRequest({
            type: 'GET',
            url: baseUrl + 'conversation/list',
        }).then(function (response) {
            state.conversationList = response.data.conversations || [];
            renderConversationList();
            if (!state.conversationList.length) {
                return ensureConversationReady();
            }
            return openConversation(state.conversationList[0].conversation_id);
        });
    }

    function createConversation() {
        if (state.pendingConversationPromise) {
            return state.pendingConversationPromise;
        }

        state.pendingConversationPromise = apiRequest({
            type: 'POST',
            url: baseUrl + 'conversation/create',
            data: JSON.stringify({ title: '新对话', mode: 'agent' }),
        }).then(function (response) {
            var conversation = response.data;
            state.currentConversationId = conversation.conversation_id;
            state.conversationList.unshift(conversation);
            renderConversationList();
            return openConversation(conversation.conversation_id).then(function () {
                return conversation.conversation_id;
            });
        }).always(function () {
            state.pendingConversationPromise = null;
        });

        return state.pendingConversationPromise;
    }

    function ensureConversationReady() {
        if (state.pendingConversationPromise) {
            return state.pendingConversationPromise.then(function (conversationId) {
                return conversationId || state.currentConversationId;
            });
        }
        if (state.currentConversationId) {
            return $.Deferred().resolve(state.currentConversationId).promise();
        }
        return createConversation().then(function (conversationId) {
            return conversationId || state.currentConversationId;
        });
    }

    function sendToConversation(conversationId, text) {
        var imageUrls = state.pendingImageUrls.slice();
        appendUserMessage(composeUserMessage(text, imageUrls), false);
        state.pendingImageUrls = [];
        renderImagePreview();
        setConversationState(true);
        $('#emptyAssistantMessage').hide();
        showLoading();

        return apiRequest({
            type: 'POST',
            url: baseUrl + 'conversation/chat',
            data: JSON.stringify({
                conversation_id: conversationId,
                query: text,
                image_urls: imageUrls,
                mode: 'agent',
            }),
        }).then(function (data) {
            hideLoading();
            newRecievedMessage(data.message);
            state.currentConversationId = conversationId;
            state.currentConversationMessages = (data.data.conversation && data.data.conversation.messages) || state.currentConversationMessages;
            state.currentConversationDocuments = (data.data.conversation && data.data.conversation.documents) || state.currentConversationDocuments;
            syncConversationSummary(data.data.conversation);
            renderDocumentList();
        }).fail(function (xhr, textStatus, errorThrown) {
            hideLoading();
            var serverMessage = '';
            if (xhr && xhr.responseJSON && xhr.responseJSON.message) {
                serverMessage = xhr.responseJSON.message;
            } else if (xhr && xhr.responseText) {
                serverMessage = xhr.responseText;
            }
            newRecievedMessage(serverMessage || errorThrown || textStatus || 'Internal Server Error');
        });
    }

    function uploadImage(file) {
        if (!file) {
            return;
        }
        var fileName = (file.name || '').toLowerCase();
        var mimeType = (file.type || '').toLowerCase();
        var hasSupportedMime = /^image\/(png|jpeg|webp)$/.test(mimeType);
        var hasSupportedExtension = /\.(png|jpg|jpeg|webp)$/.test(fileName);
        if (!hasSupportedMime && !hasSupportedExtension) {
            $('#uploadHint').text('仅支持 png、jpg、jpeg、webp 图片。');
            return;
        }

        return ensureConversationReady().then(function (conversationId) {
            if (!conversationId) {
                $('#uploadHint').text('会话初始化失败，无法上传图片。');
                return;
            }

            var formData = new FormData();
            formData.append('conversation_id', conversationId);
            formData.append('file', file);
            $('#uploadHint').text('正在上传图片，请稍候...');

            return $.ajax({
                type: 'POST',
                url: baseUrl + 'conversation/image/upload',
                data: formData,
                processData: false,
                contentType: false,
                dataType: 'json',
            }).done(function (response) {
                if (response && response.code && response.code !== 'success') {
                    $('#uploadHint').text(response.message || '图片上传失败');
                    return;
                }
                var imageUrl = response.data && response.data.image_url;
                if (!imageUrl) {
                    $('#uploadHint').text('图片上传失败');
                    return;
                }
                state.currentConversationId = conversationId;
                state.pendingImageUrls.push(imageUrl);
                renderImagePreview();
                $('#uploadHint').text('图片已加入当前输入，可直接提问。');
            }).fail(function (xhr) {
                var message = (xhr.responseJSON && xhr.responseJSON.message) || '图片上传失败';
                $('#uploadHint').text(message);
            });
        }).fail(function () {
            $('#uploadHint').text('会话初始化失败，无法上传图片。');
        });
    }

    function openConversation(conversationId) {
        return apiRequest({
            type: 'GET',
            url: baseUrl + 'conversation/detail',
            data: { conversation_id: conversationId },
        }).then(function (response) {
            var detail = response.data;
            state.currentConversationId = detail.conversation_id;
            state.currentConversationMessages = detail.messages || [];
            state.currentConversationDocuments = detail.documents || [];
            state.pendingImageUrls = [];
            setConversationState(state.currentConversationMessages.length > 0);
            renderConversationList();
            renderDocumentList();
            renderImagePreview();
            renderMessages();
            syncConversationSummary(detail);
            $('#uploadHint').text('支持 txt、pdf、docx。doc 需要先转成 docx。');
        });
    }

    function send(text) {
        if ((!text || !text.trim()) && !state.pendingImageUrls.length) {
            return;
        }
        return ensureConversationReady().then(function (conversationId) {
            if (!conversationId) {
                newRecievedMessage('会话初始化失败，请重试。');
                return;
            }
            return sendToConversation(conversationId, text);
        });
    }

    function uploadDocument(file) {
        if (!file) {
            return;
        }
        return ensureConversationReady().then(function (conversationId) {
            if (!conversationId) {
                $('#uploadHint').text('会话初始化失败，无法上传文档。');
                return;
            }

            var formData = new FormData();
            formData.append('conversation_id', conversationId);
            formData.append('file', file);
            $('#uploadHint').text('正在上传并建立索引，请稍候...');

            return $.ajax({
                type: 'POST',
                url: baseUrl + 'document/upload',
                data: formData,
                processData: false,
                contentType: false,
                dataType: 'json',
            }).done(function (response) {
                if (response && response.code && response.code !== 'success') {
                    $('#uploadHint').text(response.message || '上传失败');
                    return;
                }
                state.currentConversationId = conversationId;
                $('#uploadHint').text('文档已入库，可直接开始提问。');
                openConversation(conversationId);
            }).fail(function (xhr) {
                var message = (xhr.responseJSON && xhr.responseJSON.message) || '上传失败';
                $('#uploadHint').text(message);
            });
        }).fail(function () {
            $('#uploadHint').text('会话初始化失败，无法上传文档。');
        });
    }

    function deleteDocument(documentId) {
        return apiRequest({
            type: 'POST',
            url: baseUrl + 'document/delete',
            data: JSON.stringify({ document_id: documentId }),
        }).then(function () {
            return openConversation(state.currentConversationId);
        });
    }

    function submitCurrentInput() {
        var input = $('textarea.input')[0];
        if (!input) {
            return;
        }
        var value = input.value.trim();
        if (!value && !state.pendingImageUrls.length) {
            return;
        }
        input.value = '';
        send(value);
    }

    // ==============================
    // JD 分析功能
    // ==============================

    function renderAnalysisResult(data) {
        if (!data) {
            return;
        }
        var jdAnalysis = data.jd_analysis || {};
        var scoring = data.scoring || {};

        // 岗位名称
        $('#analysisJobRole').text(jdAnalysis.job_role || '-');

        // 总分
        $('#analysisTotalScore').text(scoring.total_score || 0);

        // 关键词
        var $keywords = $('#analysisKeywords').empty();
        var keywords = jdAnalysis.keywords || [];
        if (keywords.length) {
            keywords.forEach(function (kw) {
                $keywords.append($('<span/>', { 'class': 'keyword-tag', text: kw }));
            });
        } else {
            $keywords.text('-');
        }

        // 维度评分
        var $dimensions = $('#dimensionGrid').empty();
        var dimensions = scoring.dimensions || {};
        var dimLabels = {
            'skill_match': '技能匹配度',
            'project_relevance': '项目相关性',
            'expression_quality': '表达质量',
            'job_fitness': '岗位适配度',
        };
        var dimColors = {
            'skill_match': '#10a37f',
            'project_relevance': '#3b82f6',
            'expression_quality': '#f59e0b',
            'job_fitness': '#8b5cf6',
        };
        Object.keys(dimLabels).forEach(function (key) {
            var score = dimensions[key] || 0;
            var label = dimLabels[key];
            var color = dimColors[key] || '#10a37f';
            var $dim = $('<div/>', { 'class': 'dimension-item' });
            $dim.append($('<span/>', { 'class': 'dimension-label', text: label }));
            $dim.append(
                $('<div/>', { 'class': 'dimension-bar-bg' }).append(
                    $('<div/>', {
                        'class': 'dimension-bar-fill',
                        style: 'width: ' + score + '%; background-color: ' + color + ';',
                    })
                )
            );
            $dim.append($('<span/>', { 'class': 'dimension-score', text: score }));
            $dimensions.append($dim);
        });

        // 优势
        var $strengths = $('#analysisStrengths').empty();
        (scoring.strengths || []).forEach(function (item) {
            $strengths.append($('<li/>', { text: item }));
        });

        // 缺口
        var $gaps = $('#analysisGaps').empty();
        (scoring.gaps || []).forEach(function (item) {
            $gaps.append($('<li/>', { text: item }));
        });

        // 建议
        var $suggestions = $('#analysisSuggestions').empty();
        (scoring.suggestions || []).forEach(function (item) {
            $suggestions.append($('<li/>', { text: item }));
        });

        $('#analysisLoading').hide();
        $('#analysisResult').show();
        $('#analysisPanel').show();
    }

    function startJdAnalysis() {
        var jdText = $('#jdInput').val().trim();
        if (!jdText) {
            $('#jdStatus').text('请先粘贴职位描述（JD）');
            return;
        }

        var conversationId = state.currentConversationId;
        if (!conversationId) {
            $('#jdStatus').text('请先创建或选择一个会话');
            return;
        }

        $('#jdStatus').text('正在分析...');
        $('#startAnalysis').prop('disabled', true);
        $('#analysisLoading').show();
        $('#analysisResult').hide();
        $('#analysisPanel').show();

        apiRequest({
            type: 'POST',
            url: baseUrl + 'job/analyze',
            data: JSON.stringify({
                conversation_id: conversationId,
                jd_text: jdText,
            }),
        }).then(function (response) {
            $('#jdStatus').text('分析完成');
            renderAnalysisResult(response.data);
        }).fail(function (xhr, textStatus, errorThrown) {
            var message = (xhr.responseJSON && xhr.responseJSON.message) || '分析失败，请稍后重试';
            $('#jdStatus').text(message);
            $('#analysisLoading').hide();
            $('#analysisResult').hide();
            $('#analysisPanel').show();
            // 移除之前的错误信息，显示新错误
            $('#analysisBody').find('.analysis-error').remove();
            $('#analysisBody').append(
                $('<div/>', { 'class': 'analysis-error', text: message })
            );
        }).always(function () {
            $('#startAnalysis').prop('disabled', false);
        });
    }

    function loadLatestAnalysis() {
        var conversationId = state.currentConversationId;
        if (!conversationId) {
            return;
        }

        apiRequest({
            type: 'GET',
            url: baseUrl + 'job/analysis/latest',
            data: { conversation_id: conversationId },
        }).then(function (response) {
            if (response.data && response.data.job_role) {
                var jdAnalysis = {
                    job_role: response.data.job_role,
                    keywords: response.data.keywords || [],
                };
                var scoring = {
                    total_score: response.data.total_score,
                    dimensions: response.data.dimensions || {},
                    strengths: response.data.strengths || [],
                    gaps: response.data.gaps || [],
                    suggestions: response.data.suggestions || [],
                };
                latestAnalysisId = response.data.id;
                renderAnalysisResult({ jd_analysis: jdAnalysis, scoring: scoring });
                // 恢复 JD 文本到输入框（作为提示）
                $('#jdInput').val('[已有分析结果，可重新粘贴 JD 再次分析]');
            }
        }).fail(function () {
            // 没有历史分析结果，忽略
        });
    }

    function loadInterviewSessions(conversationId) {
        if (!conversationId) {
            return;
        }

        apiRequest({
            type: 'GET',
            url: baseUrl + 'interview/list',
            data: { conversation_id: conversationId },
        }).then(function (response) {
            var sessions = (response.data && response.data.sessions) || [];
            var $container = $('#interviewHistory');
            $container.empty();
            if (sessions.length > 0) {
                $('#interviewStatus').text('有 ' + sessions.length + ' 场面试记录');
                sessions.slice(0, 3).forEach(function (s) {
                    var statusClass = 'ih-status-' + (s.status === 'completed' ? 'completed' : 'in_progress');
                    var statusLabel = s.status === 'completed' ? '✓' : '▶';
                    var $item = $('<div/>', {
                        'class': 'interview-history-item',
                        'data-session-id': s.session_id,
                    });
                    $item.append($('<span/>', {
                        'class': 'ih-status ' + statusClass,
                        text: statusLabel,
                    }));
                    $item.append($('<span/>', {
                        text: s.direction + ' · ' + (s.round_count || 0) + '轮' + (s.total_score ? ' · ' + s.total_score + '分' : ''),
                    }));
                    $item.on('click', function () {
                        loadInterviewDetail(s.session_id);
                    });
                    $container.append($item);
                });
            }
        }).fail(function () {
            // 忽略
        });
    }

    function loadInterviewDetail(sessionId) {
        apiRequest({
            type: 'GET',
            url: baseUrl + 'interview/detail',
            data: { session_id: sessionId },
        }).then(function (response) {
            var data = response.data;
            if (!data || !data.session) {
                return;
            }
            var session = data.session;
            var messages = data.messages || [];

            $('#interviewPanel').show();
            $('#interviewQuestionArea').hide();
            $('#interviewFeedback').hide();
            var summaryHtml = '<h4>面试回顾</h4>' +
                '<p><strong>方向：</strong>' + session.direction + '</p>' +
                '<p><strong>状态：</strong>' + (session.status === 'completed' ? '已完成' : '进行中') + '</p>' +
                '<p><strong>轮次：</strong>' + (session.round_count || 0) + ' 轮</p>' +
                (session.total_score ? '<p><strong>总分：</strong>' + session.total_score + '/100</p>' : '') +
                (session.overall_summary ? '<hr style="border:none;border-top:1px solid var(--border-soft);margin:12px 0;"><p><strong>总结：</strong></p><p>' + escapeHtml(session.overall_summary) + '</p>' : '');

            if (messages.length > 0) {
                summaryHtml += '<hr style="border:none;border-top:1px solid var(--border-soft);margin:12px 0;"><p><strong>对话记录：</strong></p>';
                messages.forEach(function (msg) {
                    if (msg.msg_type === 'question') {
                        summaryHtml += '<p style="color:var(--accent);font-weight:600;margin:8px 0 4px;">❓ ' + escapeHtml(msg.content) + '</p>';
                    } else if (msg.msg_type === 'answer') {
                        summaryHtml += '<p style="margin:4px 0 4px 12px;color:var(--text-secondary);">💬 ' + escapeHtml(msg.content) + '</p>';
                    } else if (msg.msg_type === 'evaluation') {
                        summaryHtml += '<p style="margin:4px 0 8px 12px;font-size:13px;color:#d97706;">📝 ' + escapeHtml(msg.content) + (msg.score ? ' <strong>评分：' + msg.score + '/100</strong>' : '') + '</p>';
                    }
                });
            }

            $('#interviewSummary').html(summaryHtml).show();
            $('#interviewSessionInfo').text('面试回顾 · ' + session.direction);
            interviewState.sessionId = sessionId;
        }).fail(function () {
            // 忽略
        });
    }

    // ==============================
    // 项目经历优化功能
    // ==============================

    function renderProjectResult(data) {
        if (!data) {
            return;
        }

        // 原描述问题
        var $issues = $('#projectIssues').empty();
        (data.original_issues || []).forEach(function (item) {
            $issues.append($('<li/>', { text: item }));
        });

        // 优化版本
        $('#projectImproved').text(data.improved_version || '-');
        $('#projectPythonVersion').text(data.python_backend_version || '-');
        $('#projectAgentVersion').text(data.agent_version || '-');

        $('#projectLoading').hide();
        $('#projectResult').show();
        $('#projectPanel').show();
    }

    function startProjectRewrite() {
        var projectText = $('#projectInput').val().trim();
        if (!projectText) {
            $('#projectStatus').text('请先粘贴项目描述');
            return;
        }

        var conversationId = state.currentConversationId;
        if (!conversationId) {
            $('#projectStatus').text('请先创建或选择一个会话');
            return;
        }

        $('#projectStatus').text('正在优化...');
        $('#startProjectRewrite').prop('disabled', true);
        $('#projectLoading').show();
        $('#projectResult').hide();
        $('#projectPanel').show();

        apiRequest({
            type: 'POST',
            url: baseUrl + 'resume/project/rewrite',
            data: JSON.stringify({
                conversation_id: conversationId,
                project_description: projectText,
            }),
        }).then(function (response) {
            $('#projectStatus').text('优化完成');
            renderProjectResult(response.data);
        }).fail(function (xhr, textStatus, errorThrown) {
            var message = (xhr.responseJSON && xhr.responseJSON.message) || '优化失败，请稍后重试';
            $('#projectStatus').text(message);
            $('#projectLoading').hide();
            $('#projectResult').hide();
        }).always(function () {
            $('#startProjectRewrite').prop('disabled', false);
        });
    }

    // ==============================
    // 模拟面试功能
    // ==============================

    var interviewState = {
        sessionId: '',
        questionIndex: 0,
        totalQuestions: 0,
        questions: [],
    };

    function resetInterviewState() {
        interviewState.sessionId = '';
        interviewState.questionIndex = 0;
        interviewState.totalQuestions = 0;
        interviewState.questions = [];
    }

    function startInterview() {
        var conversationId = state.currentConversationId;
        if (!conversationId) {
            $('#interviewStatus').text('请先创建或选择一个会话');
            return;
        }

        var direction = $('#interviewDirection').val();

        $('#interviewStatus').text('正在生成面试题...');
        $('#startInterview').prop('disabled', true);
        $('#interviewPanel').show();
        $('#interviewLoading').show();
        $('#interviewQuestionArea').hide();
        $('#interviewFeedback').hide();
        $('#interviewSummary').hide();

        resetInterviewState();

        apiRequest({
            type: 'POST',
            url: baseUrl + 'interview/start',
            data: JSON.stringify({
                conversation_id: conversationId,
                direction: direction,
            }),
        }).then(function (response) {
            var data = response.data;
            interviewState.sessionId = data.session_id;
            interviewState.questions = data.questions || [];
            interviewState.questionIndex = data.question_index || 0;
            interviewState.totalQuestions = data.total_questions || 0;

            $('#interviewStatus').text('面试已开始');
            $('#interviewLoading').hide();
            $('#interviewFeedback').hide();
            $('#interviewSummary').hide();
            $('#interviewSessionInfo').text(
                '面试进行中（' + directionLabel(direction) + '）· 共 ' + interviewState.totalQuestions + ' 题'
            );

            // 显示第一题
            var currentQ = data.current_question || {};
            showInterviewQuestion(currentQ.question || '', interviewState.questionIndex + 1);
        }).fail(function (xhr, textStatus, errorThrown) {
            var message = (xhr.responseJSON && xhr.responseJSON.message) || '面试启动失败';
            $('#interviewStatus').text(message);
            $('#interviewLoading').hide();
            $('#interviewQuestionArea').hide();
        }).always(function () {
            $('#startInterview').prop('disabled', false);
        });
    }

    function directionLabel(direction) {
        var labels = {
            'general': '通用方向',
            'python_backend': 'Python 后端',
            'agent_ai': 'Agent / AI 应用',
        };
        return labels[direction] || direction;
    }

    function showInterviewQuestion(question, index) {
        $('#interviewQuestion').text('第 ' + index + ' 题：' + question);
        $('#interviewAnswer').val('');
        $('#interviewQuestionArea').show();
        $('#interviewFeedback').hide();
        $('#interviewSummary').hide();
        $('#submitInterviewAnswer').prop('disabled', false);
    }

    function submitInterviewAnswer() {
        var answer = $('#interviewAnswer').val().trim();
        if (!answer) {
            return;
        }

        if (!interviewState.sessionId) {
            return;
        }

        $('#submitInterviewAnswer').prop('disabled', true);
        $('#interviewLoading').show();
        $('#interviewFeedback').hide();

        apiRequest({
            type: 'POST',
            url: baseUrl + 'interview/answer',
            data: JSON.stringify({
                session_id: interviewState.sessionId,
                answer: answer,
                question_index: interviewState.questionIndex,
            }),
        }).then(function (response) {
            var data = response.data;
            $('#interviewLoading').hide();

            if (data.action === 'summary') {
                // 面试结束
                $('#interviewQuestionArea').hide();
                $('#interviewSummary').show().html(
                    '<h4>🎉 面试结束</h4>' +
                    '<p><strong>评分：</strong>' + (data.score || 0) + '/100</p>' +
                    '<p><strong>面试评价：</strong></p>' +
                    '<p>' + escapeHtml(data.evaluation || '') + '</p>' +
                    '<hr style="border:none;border-top:1px solid var(--border-soft);margin:12px 0;">' +
                    '<p><strong>总结：</strong></p>' +
                    '<p>' + escapeHtml(data.overall_summary || '') + '</p>'
                );
                $('#interviewSessionInfo').text('面试已结束 · 总分 ' + (data.score || 0));
            } else {
                // 继续面试
                var evalHtml = '<span class="feedback-score">评分：' + (data.score || 0) + '/100</span>';
                evalHtml += '<p>' + escapeHtml(data.evaluation || '') + '</p>';
                $('#interviewFeedback').html(evalHtml).show();

                // 显示下一题
                setTimeout(function () {
                    var nextQ = data.next_question || '';
                    interviewState.questionIndex = data.question_index || 0;
                    if (nextQ) {
                        showInterviewQuestion(nextQ, interviewState.questionIndex + 1);
                    } else {
                        $('#interviewQuestionArea').hide();
                    }
                }, 1500);
            }
        }).fail(function (xhr, textStatus, errorThrown) {
            var message = (xhr.responseJSON && xhr.responseJSON.message) || '提交失败';
            $('#interviewLoading').hide();
            $('#interviewFeedback').html('<p style="color:#ef4444;">' + escapeHtml(message) + '</p>').show();
            $('#submitInterviewAnswer').prop('disabled', false);
        });
    }

    // ==============================
    // 截图分析功能
    // ==============================

    function startScreenshotAnalysis() {
        var conversationId = state.currentConversationId;
        if (!conversationId) {
            $('#jdStatus').text('请先创建或选择一个会话');
            return;
        }
        $('#screenshotInput').trigger('click');
    }

    function uploadScreenshotAndAnalyze(file) {
        if (!file) { return; }
        var fileName = (file.name || '').toLowerCase();
        var mimeType = (file.type || '').toLowerCase();
        if (!/^image\/(png|jpeg|webp)$/.test(mimeType) && !/\.(png|jpg|jpeg|webp)$/.test(fileName)) {
            $('#jdStatus').text('仅支持 png、jpg、jpeg、webp 图片。');
            return;
        }
        var conversationId = state.currentConversationId;
        if (!conversationId) { $('#jdStatus').text('请先创建或选择一个会话'); return; }

        var formData = new FormData();
        formData.append('conversation_id', conversationId);
        formData.append('file', file);
        $('#jdStatus').text('正在上传截图...');
        $('#startScreenshotAnalysis').prop('disabled', true);

        $.ajax({
            type: 'POST',
            url: baseUrl + 'conversation/image/upload',
            data: formData, processData: false, contentType: false, dataType: 'json',
        }).done(function (response) {
            if (!response || (response.code && response.code !== 'success')) {
                $('#jdStatus').text((response && response.message) || '图片上传失败');
                $('#startScreenshotAnalysis').prop('disabled', false);
                return;
            }
            var imageUrl = response.data && response.data.image_url;
            if (!imageUrl) { $('#jdStatus').text('图片上传失败'); $('#startScreenshotAnalysis').prop('disabled', false); return; }

            $('#jdStatus').text('正在分析截图中的 JD...');
            $('#analysisLoading').show();
            $('#analysisResult').hide();
            $('#analysisPanel').show();

            apiRequest({
                type: 'POST',
                url: baseUrl + 'job/analyze-from-screenshot',
                data: JSON.stringify({ conversation_id: conversationId, image_url: imageUrl }),
            }).then(function (analysisResponse) {
                $('#jdStatus').text('截图分析完成');
                renderAnalysisResult(analysisResponse.data);
            }).fail(function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) || '截图分析失败';
                $('#jdStatus').text(msg);
                $('#analysisLoading').hide();
            }).always(function () {
                $('#startScreenshotAnalysis').prop('disabled', false);
            });
        }).fail(function (xhr) {
            var msg = (xhr.responseJSON && xhr.responseJSON.message) || '图片上传失败';
            $('#jdStatus').text(msg);
            $('#startScreenshotAnalysis').prop('disabled', false);
        });
    }

    // ==============================
    // 雷达图
    // ==============================

    var radarChartInstance = null;

    function renderRadarChart(dimensions) {
        var canvas = document.getElementById('radarChart');
        if (!canvas) { return; }
        if (radarChartInstance) { radarChartInstance.destroy(); radarChartInstance = null; }

        radarChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'radar',
            data: {
                labels: ['技能匹配度', '项目相关性', '表达质量', '岗位适配度'],
                datasets: [{
                    label: '评分',
                    data: [dimensions.skill_match || 0, dimensions.project_relevance || 0, dimensions.expression_quality || 0, dimensions.job_fitness || 0],
                    backgroundColor: 'rgba(16, 163, 127, 0.2)',
                    borderColor: 'rgba(16, 163, 127, 0.9)',
                    borderWidth: 2,
                    pointBackgroundColor: 'rgba(16, 163, 127, 0.9)',
                    pointBorderColor: '#fff',
                    pointRadius: 4,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: true,
                scales: { r: { beginAtZero: true, max: 100, ticks: { stepSize: 20, font: { size: 10 } }, grid: { color: 'rgba(0,0,0,0.08)' }, angleLines: { color: 'rgba(0,0,0,0.08)' }, pointLabels: { font: { size: 11 } } } },
                plugins: { legend: { display: false } },
            }
        });
    }

    var _origRenderAnalysisResult = renderAnalysisResult;
    renderAnalysisResult = function (data) {
        _origRenderAnalysisResult(data);
        if (data && data.scoring && data.scoring.dimensions) {
            renderRadarChart(data.scoring.dimensions);
        }
    };

    // ==============================
    // 简历版本管理
    // ==============================

    function loadResumeVersions(conversationId) {
        if (!conversationId) { $('#versionSelector').hide(); return; }
        apiRequest({
            type: 'GET', url: baseUrl + 'resume/versions/list', data: { conversation_id: conversationId },
        }).then(function (response) {
            var versions = (response.data && response.data.versions) || [];
            var $select = $('#resumeVersionSelect');
            $select.empty().append($('<option/>', { value: '', text: '选择版本查看分数' }));
            if (versions.length > 1) {
                versions.forEach(function (v) {
                    var label = 'v' + v.version_number + ' ' + (v.original_name || '') + (v.total_score !== null ? ' [' + v.total_score + '分]' : '');
                    $select.append($('<option/>', { value: v.version_id, text: label }));
                });
                $('#versionSelector').show();
            } else {
                $('#versionSelector').hide();
            }
        }).fail(function () { $('#versionSelector').hide(); });
    }

    // ==============================
    // 知识库功能
    // ==============================

    function loadKnowledgeStatus() {
        apiRequest({ type: 'GET', url: baseUrl + 'knowledge/status' }).then(function (response) {
            var data = response.data || {};
            $('#knowledgeStatus').text(data.index_exists ? ('已就绪（' + (data.total_documents || 0) + ' 篇）') : '需要重建索引');
        }).fail(function () { $('#knowledgeStatus').text('无法获取状态'); });
    }

    function searchKnowledge() {
        var query = $('#knowledgeQuery').val().trim();
        if (!query) { return; }
        $('#knowledgeStatus').text('正在搜索...');
        apiRequest({ type: 'GET', url: baseUrl + 'knowledge/query', data: { query: query, k: 4 } }).then(function (response) {
            var results = (response.data && response.data.results) || [];
            var $container = $('#knowledgeResults').empty();
            if (!results.length) {
                $container.append($('<div/>', { 'class': 'knowledge-result-item', text: '未找到相关内容' }));
            } else {
                results.forEach(function (r) {
                    var $item = $('<div/>', { 'class': 'knowledge-result-item' });
                    $item.append($('<div/>', { 'class': 'kr-title', text: r.title }));
                    $item.append($('<span/>', { 'class': 'kr-category', text: r.category }));
                    $item.append($('<div/>', { 'class': 'kr-content', text: r.content }));
                    $container.append($item);
                });
            }
            $('#knowledgeStatus').text('找到 ' + results.length + ' 条结果');
        }).fail(function () { $('#knowledgeStatus').text('搜索失败'); });
    }

    function rebuildKnowledge() {
        $('#knowledgeStatus').text('正在重建知识库索引...');
        apiRequest({ type: 'POST', url: baseUrl + 'knowledge/rebuild' }).then(function (response) {
            $('#knowledgeStatus').text(response.message || '重建完成');
        }).fail(function (xhr) {
            $('#knowledgeStatus').text((xhr.responseJSON && xhr.responseJSON.message) || '重建失败');
        });
    }

    // ==============================
    // 导出功能
    // ==============================

    var latestAnalysisId = null;

    function exportAnalysis() {
        if (!latestAnalysisId) {
            var conversationId = state.currentConversationId;
            if (!conversationId) { return; }
            apiRequest({ type: 'GET', url: baseUrl + 'job/analysis/list', data: { conversation_id: conversationId } }).then(function (response) {
                var analyses = (response.data && response.data.analyses) || [];
                if (analyses.length > 0) { doExportAnalysis(analyses[0].id); }
            });
            return;
        }
        doExportAnalysis(latestAnalysisId);
    }

    function doExportAnalysis(analysisId) {
        apiRequest({ type: 'GET', url: baseUrl + 'export/analysis', data: { analysis_id: analysisId } }).then(function (response) {
            var md = response.data && response.data.markdown;
            if (md) { downloadMarkdown(md, 'JD分析报告.md'); }
        }).fail(function (xhr) {
            $('#jdStatus').text((xhr.responseJSON && xhr.responseJSON.message) || '导出失败');
        });
    }

    function exportProjectRewrite() {
        var issues = [];
        $('#projectIssues li').each(function () { issues.push($(this).text()); });
        var improved = $('#projectImproved').text();
        if (!improved || improved === '-') { return; }
        var result = {
            original_issues: issues, improved_version: improved,
            python_backend_version: $('#projectPythonVersion').text(),
            agent_version: $('#projectAgentVersion').text(),
        };
        apiRequest({ type: 'POST', url: baseUrl + 'export/project-rewrite', data: JSON.stringify({ result: result }) }).then(function (response) {
            var md = response.data && response.data.markdown;
            if (md) { downloadMarkdown(md, '项目优化报告.md'); }
        }).fail(function () {
            downloadMarkdown(generateLocalProjectMd(result), '项目优化报告.md');
        });
    }

    function exportInterview() {
        if (!interviewState.sessionId) { return; }
        apiRequest({ type: 'GET', url: baseUrl + 'export/interview', data: { session_id: interviewState.sessionId } }).then(function (response) {
            var md = response.data && response.data.markdown;
            if (md) { downloadMarkdown(md, '模拟面试回顾.md'); }
        }).fail(function () {});
    }

    function generateLocalProjectMd(result) {
        var lines = ['# 项目经历优化报告', '', '---', '', '## 原描述问题', ''];
        (result.original_issues || []).forEach(function (i) { lines.push('- ' + i); });
        lines.push('', '---', '', '## 优化版本（通用）', '', result.improved_version || '', '');
        lines.push('---', '', '## Python 后端导向版本', '', result.python_backend_version || '', '');
        lines.push('---', '', '## Agent / AI 导向版本', '', result.agent_version || '', '');
        lines.push('', '---', '', '*由 求职助手 Agent 自动生成*');
        return lines.join('\n');
    }

    function downloadMarkdown(markdown, filename) {
        var blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var $a = $('<a/>', { href: url, download: filename, style: 'display:none;' });
        $('body').append($a);
        $a[0].click();
        setTimeout(function () { URL.revokeObjectURL(url); $a.remove(); }, 1000);
    }

    // ==============================
    // 事件绑定
    // ==============================

    $(document).ready(function () {
        setConversationState(false);

        $('textarea').keypress(function (event) {
            if (event.which === 13 && !event.shiftKey) {
                event.preventDefault();
                submitCurrentInput();
            }
        });

        $('#sendMessage').click(function () {
            submitCurrentInput();
        });

        $('#createConversation').click(function () {
            state.currentConversationId = '';
            state.currentConversationMessages = [];
            state.currentConversationDocuments = [];
            state.pendingImageUrls = [];
            renderImagePreview();
            createConversation();
        });

        $('#triggerUpload').click(function () {
            $('#documentInput').trigger('click');
        });

        $('#triggerImageUpload').click(function () {
            $('#imageInput').trigger('click');
        });

        $('#documentInput').change(function (event) {
            var file = event.target.files && event.target.files[0];
            uploadDocument(file);
            event.target.value = '';
        });

        $('#imageInput').change(function (event) {
            var file = event.target.files && event.target.files[0];
            uploadImage(file);
            event.target.value = '';
        });

        $('.conversation-list').on('click', '.conversation-item', function () {
            var conversationId = $(this).data('id');
            openConversation(conversationId);
            loadLatestAnalysis();
            loadInterviewSessions(conversationId);
            loadResumeVersions(conversationId);
        });

        $('.composer-panel').on('click', '.image-preview-remove', function () {
            var index = Number($(this).data('index'));
            state.pendingImageUrls = state.pendingImageUrls.filter(function (_, itemIndex) {
                return itemIndex !== index;
            });
            renderImagePreview();
        });

        $('.document-list').on('click', '.document-delete', function () {
            deleteDocument($(this).data('id'));
        });

        $('.prompt-chip').click(function () {
            var prompt = $(this).data('prompt');
            if (prompt) {
                $('.input').val(prompt);
                submitCurrentInput();
            }
        });

        // JD 分析事件
        $('#startAnalysis').click(function () {
            startJdAnalysis();
        });

        $('#closeAnalysis').click(function () {
            $('#analysisPanel').hide();
        });

        // 项目优化事件
        $('#startProjectRewrite').click(function () {
            startProjectRewrite();
        });

        $('#closeProject').click(function () {
            $('#projectPanel').hide();
        });

        $('#copyProjectVersion').click(function () {
            var text = $('#projectImproved').text();
            if (text && text !== '-') {
                navigator.clipboard.writeText(text).then(function () {
                    $('#projectStatus').text('已复制优化版本');
                }).catch(function () {
                    // Fallback
                    var $textarea = $('<textarea>');
                    $textarea.val(text);
                    $('body').append($textarea);
                    $textarea.select();
                    document.execCommand('copy');
                    $textarea.remove();
                    $('#projectStatus').text('已复制优化版本');
                });
            }
        });

        // 模拟面试事件
        $('#startInterview').click(function () {
            startInterview();
        });

        $('#closeInterview').click(function () {
            $('#interviewPanel').hide();
            resetInterviewState();
        });

        $('#submitInterviewAnswer').click(function () {
            submitInterviewAnswer();
        });

        // Interview textarea: Ctrl/Cmd + Enter to submit
        $('#interviewAnswer').keydown(function (event) {
            if ((event.ctrlKey || event.metaKey) && event.which === 13) {
                event.preventDefault();
                submitInterviewAnswer();
            }
        });

        // 截图分析事件
        $('#startScreenshotAnalysis').click(function () {
            startScreenshotAnalysis();
        });

        $('#screenshotInput').change(function (event) {
            var file = event.target.files && event.target.files[0];
            uploadScreenshotAndAnalyze(file);
            event.target.value = '';
        });

        // 版本选择
        $('#resumeVersionSelect').change(function () {
            var versionId = $(this).val();
            if (!versionId) {
                $('#versionScoreBadge').hide();
                return;
            }
            apiRequest({ type: 'GET', url: baseUrl + 'resume/versions/detail', data: { version_id: versionId } }).then(function (response) {
                var v = response.data;
                if (v && v.total_score !== null) {
                    var dims = v.dimensions || {};
                    $('#versionScoreBadge').html(
                        '总分: <strong>' + v.total_score + '</strong> | ' +
                        '技能: ' + (dims.skill_match || '-') + ' | ' +
                        '项目: ' + (dims.project_relevance || '-') + ' | ' +
                        '表达: ' + (dims.expression_quality || '-') + ' | ' +
                        '适配: ' + (dims.job_fitness || '-')
                    ).show();
                } else {
                    $('#versionScoreBadge').text('该版本暂无评分数据').show();
                }
            });
        });

        // 知识库事件
        $('#searchKnowledge').click(function () { searchKnowledge(); });
        $('#knowledgeQuery').keypress(function (e) {
            if (e.which === 13) { e.preventDefault(); searchKnowledge(); }
        });
        $('#rebuildKnowledge').click(function () { rebuildKnowledge(); });

        // 导出事件
        $('#exportAnalysisBtn').click(function () { exportAnalysis(); });
        $('#exportProjectBtn').click(function () { exportProjectRewrite(); });
        $('#exportInterviewBtn').click(function () { exportInterview(); });

        // 加载简历版本和知识库状态
        loadConversationList().then(function () {
            if (state.currentConversationId) {
                loadInterviewSessions(state.currentConversationId);
                loadResumeVersions(state.currentConversationId);
            }
            loadKnowledgeStatus();
        }).fail(function (xhr) {
            var message = (xhr.responseJSON && xhr.responseJSON.message) || '初始化会话失败';
            $('#uploadHint').text(message);
        });
    });
})();