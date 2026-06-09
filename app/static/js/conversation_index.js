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
                success: function (response) {
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
                },
                error: function (xhr) {
                    var message = (xhr.responseJSON && xhr.responseJSON.message) || '图片上传失败';
                    $('#uploadHint').text(message);
                },
            });
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
        if (!file || !state.currentConversationId) {
            return;
        }
        var formData = new FormData();
        formData.append('conversation_id', state.currentConversationId);
        formData.append('file', file);
        $('#uploadHint').text('正在上传并建立索引，请稍候...');

        return $.ajax({
            type: 'POST',
            url: baseUrl + 'document/upload',
            data: formData,
            processData: false,
            contentType: false,
            success: function (response) {
                if (response && response.code && response.code !== 'success') {
                    $('#uploadHint').text(response.message || '上传失败');
                    return;
                }
                $('#uploadHint').text('文档已入库，可直接开始提问。');
                openConversation(state.currentConversationId);
            },
            error: function (xhr) {
                var message = (xhr.responseJSON && xhr.responseJSON.message) || '上传失败';
                $('#uploadHint').text(message);
            },
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

        loadConversationList().fail(function (xhr) {
            var message = (xhr.responseJSON && xhr.responseJSON.message) || '初始化会话失败';
            $('#uploadHint').text(message);
        });
    });
})();