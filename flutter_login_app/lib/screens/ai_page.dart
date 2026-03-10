import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';

// ─── Models ──────────────────────────────────────────────────────────────────

enum MessageRole { user, bot }

class ChatMessage {
  final String content;
  final MessageRole role;
  final String? intent;
  final DateTime timestamp;

  ChatMessage({
    required this.content,
    required this.role,
    this.intent,
  }) : timestamp = DateTime.now();
}

// ─── Quick Actions ────────────────────────────────────────────────────────────

const _quickActions = [
  ("💸 Record", "I spent ₹200 on food"),
  ("📊 This month", "How much did I spend this month?"),
  ("🔍 Category", "How much did I spend on transport?"),
  ("📋 List", "Show today's expenses"),
  ("🎯 Budget", "Am I over budget?"),
  ("📈 Analysis", "Where am I spending the most?"),
  ("💰 Savings", "How much did I save this month?"),
  ("🎁 Wishlist", "Show my wishlist progress"),
  ("🔄 Compare", "Compare this month and last month"),
  ("💡 Tips", "Give me financial tips"),
];

// ─── Intent → Badge label ─────────────────────────────────────────────────────

const _intentLabels = {
  "ADD_EXPENSE": "💸 Recorded",
  "TOTAL_EXPENSE": "📊 Summary",
  "CATEGORY_EXPENSE": "🔍 Category",
  "CHECK_BUDGET": "🎯 Budget",
  "SET_BUDGET": "🎯 Budget set",
  "SHOW_EXPENSES": "📋 Transactions",
  "SPENDING_ANALYSIS": "📈 Analysis",
  "SAVINGS_INFO": "💰 Savings",
  "COMPARE_EXPENSES": "🔄 Comparison",
  "WISHLIST_STATUS": "🎁 Wishlist",
  "WISHLIST_TIMELINE": "🎁 Goal timeline",
  "FINANCIAL_ADVICE": "💡 Advice",
  "GREETING": "👋 Hello",
  "TIME_BASED_QUERY": "🗓️ Period Summary",
  "EDIT_EXPENSE": "✏️ Modified",
  "FOLLOW_UP_QUERY": "💬 Context",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

class AIPage extends StatefulWidget {
  final int userId;
  const AIPage({super.key, required this.userId});

  @override
  State<AIPage> createState() => _AIPageState();
}

class _AIPageState extends State<AIPage> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  final _focusNode = FocusNode();

  final List<ChatMessage> _messages = [];
  bool _isLoading = false;
  bool _showQuickActions = true;

  @override
  void initState() {
    super.initState();
    _messages.add(ChatMessage(
      content: "Hi! I'm FinBot 🤖\n\n"
          "I understand natural language — just talk to me!\n\n"
          "• 'I spent ₹300 on groceries'\n"
          "• 'How much did I spend this week?'\n"
          "• 'Show my wishlist progress'\n"
          "• 'Am I over budget?'",
      role: MessageRole.bot,
    ));
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || _isLoading) return;

    _inputController.clear();
    _focusNode.unfocus();

    setState(() {
      _showQuickActions = false;
      _messages.add(ChatMessage(content: trimmed, role: MessageRole.user));
      _isLoading = true;
    });
    _scrollToBottom();

    try {
      final response = await http
          .post(
            Uri.parse("${Constants.baseUrl}/ai/chat"),
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({"message": trimmed, "user_id": widget.userId}),
          )
          .timeout(const Duration(seconds: 15));

      if (!mounted) return;
      final decoded = jsonDecode(response.body);

      if (response.statusCode == 200 && decoded['success'] == true) {
        setState(() {
          _messages.add(ChatMessage(
            content: decoded['response'],
            role: MessageRole.bot,
            intent: decoded['intent'],
          ));
        });
      } else {
        _botError(decoded['message'] ?? 'Something went wrong.');
      }
    } catch (e) {
      _botError("Connection error. Make sure the server is running.");
    } finally {
      if (mounted) setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  void _botError(String msg) {
    setState(() =>
        _messages.add(ChatMessage(content: "⚠️ $msg", role: MessageRole.bot)));
  }

  void _copyMessage(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text("Copied"),
      duration: Duration(seconds: 1),
      backgroundColor: Color(0xFF2FE6D1),
    ));
  }

  void _clearChat() {
    setState(() {
      _messages.clear();
      _showQuickActions = true;
      _messages.add(ChatMessage(
        content: "Chat cleared! What would you like to know? 💰",
        role: MessageRole.bot,
      ));
    });
  }

  // ── BUILD ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050B18),
      body: SafeArea(
        child: Column(
          children: [
            _header(),
            Expanded(
              child: GestureDetector(
                onTap: () => _focusNode.unfocus(),
                child: _messageList(),
              ),
            ),
            _inputBar(),
          ],
        ),
      ),
    );
  }

  Widget _messageList() {
    final extraItems = (_showQuickActions ? 1 : 0) + (_isLoading ? 1 : 0);
    final total = _messages.length + extraItems;

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      itemCount: total,
      itemBuilder: (ctx, index) {
        // Quick actions slot after welcome msg
        if (_showQuickActions && index == 1) return _quickActionsWidget();

        final msgIndex = (_showQuickActions && index > 1) ? index - 1 : index;

        // Thinking bubble
        if (_isLoading && msgIndex == _messages.length) {
          return _thinkingBubble();
        }

        if (msgIndex < 0 || msgIndex >= _messages.length) {
          return const SizedBox.shrink();
        }
        return _bubble(_messages[msgIndex]);
      },
    );
  }

  // ── Header ────────────────────────────────────────────────────────────────

  Widget _header() {
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.04),
            border: Border(
                bottom: BorderSide(color: Colors.white.withOpacity(0.07))),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                      colors: [Color(0xFF2FE6D1), Color(0xFF1AA898)]),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.smart_toy_outlined,
                    color: Color(0xFF061417), size: 22),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text("FinBot",
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.w600)),
                    Text("Natural language finance assistant",
                        style: TextStyle(color: Colors.white38, fontSize: 11)),
                  ],
                ),
              ),
              // Live dot
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.green.withOpacity(0.3)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                        width: 6,
                        height: 6,
                        decoration: const BoxDecoration(
                            color: Colors.green, shape: BoxShape.circle)),
                    const SizedBox(width: 5),
                    const Text("Live",
                        style: TextStyle(color: Colors.green, fontSize: 11)),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.refresh_outlined,
                    color: Colors.white38, size: 22),
                onPressed: _clearChat,
                tooltip: "Clear chat",
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Quick Actions ─────────────────────────────────────────────────────────

  Widget _quickActionsWidget() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16, top: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(bottom: 10),
            child: Text("Quick actions:",
                style: TextStyle(color: Colors.white38, fontSize: 12)),
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _quickActions
                .map((p) => GestureDetector(
                      onTap: () => _sendMessage(p.$2),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.05),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                              color: const Color(0xFF2FE6D1).withOpacity(0.3)),
                        ),
                        child: Text(p.$1,
                            style: const TextStyle(
                                color: Color(0xFF2FE6D1), fontSize: 12)),
                      ),
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }

  // ── Bubble ────────────────────────────────────────────────────────────────

  Widget _bubble(ChatMessage message) {
    final isUser = message.role == MessageRole.user;

    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment:
                isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (!isUser) ...[_botAvatar(), const SizedBox(width: 8)],
              Flexible(
                child: GestureDetector(
                  onLongPress: () => _copyMessage(message.content),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      gradient: isUser
                          ? const LinearGradient(
                              colors: [Color(0xFF2FE6D1), Color(0xFF1AA898)],
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                            )
                          : null,
                      color: isUser ? null : Colors.white.withOpacity(0.07),
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(18),
                        topRight: const Radius.circular(18),
                        bottomLeft: Radius.circular(isUser ? 18 : 4),
                        bottomRight: Radius.circular(isUser ? 4 : 18),
                      ),
                      border: isUser
                          ? null
                          : Border.all(color: Colors.white.withOpacity(0.08)),
                    ),
                    child: Text(
                      message.content,
                      style: TextStyle(
                        color: isUser ? const Color(0xFF061417) : Colors.white,
                        fontSize: 14,
                        height: 1.6,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                ),
              ),
              if (isUser) ...[const SizedBox(width: 8), _userAvatar()],
            ],
          ),
          // Intent badge under bot message
          if (!isUser && message.intent != null && message.intent != 'UNKNOWN')
            Padding(
              padding: const EdgeInsets.only(left: 42, top: 4),
              child: Text(
                _intentLabels[message.intent!] ?? message.intent!,
                style: const TextStyle(color: Colors.white24, fontSize: 10),
              ),
            ),
        ],
      ),
    );
  }

  Widget _botAvatar() => Container(
        width: 32,
        height: 32,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
              colors: [Color(0xFF2FE6D1), Color(0xFF1AA898)]),
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Icon(Icons.smart_toy_outlined,
            color: Color(0xFF061417), size: 17),
      );

  Widget _userAvatar() => Container(
        width: 32,
        height: 32,
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.08),
          borderRadius: BorderRadius.circular(10),
        ),
        child:
            const Icon(Icons.person_outline, color: Colors.white54, size: 17),
      );

  // ── Thinking Bubble ───────────────────────────────────────────────────────

  Widget _thinkingBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          _botAvatar(),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.07),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomRight: Radius.circular(18),
                bottomLeft: Radius.circular(4),
              ),
              border: Border.all(color: Colors.white.withOpacity(0.08)),
            ),
            child: const _ThinkingDots(),
          ),
        ],
      ),
    );
  }

  // ── Input Bar ─────────────────────────────────────────────────────────────

  Widget _inputBar() {
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.04),
            border:
                Border(top: BorderSide(color: Colors.white.withOpacity(0.07))),
          ),
          child: Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.07),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: Colors.white.withOpacity(0.1)),
                  ),
                  child: TextField(
                    controller: _inputController,
                    focusNode: _focusNode,
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                    maxLines: 4,
                    minLines: 1,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: const InputDecoration(
                      hintText: "e.g. 'I spent ₹200 on food'",
                      hintStyle: TextStyle(color: Colors.white38, fontSize: 13),
                      border: InputBorder.none,
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                    ),
                    onSubmitted: (val) => _sendMessage(val),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              GestureDetector(
                onTap: _isLoading
                    ? null
                    : () => _sendMessage(_inputController.text),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    gradient: _isLoading
                        ? null
                        : const LinearGradient(
                            colors: [Color(0xFF2FE6D1), Color(0xFF1AA898)]),
                    color: _isLoading ? Colors.white10 : null,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: _isLoading
                      ? const Center(
                          child: SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              color: Color(0xFF2FE6D1),
                              strokeWidth: 2,
                            ),
                          ),
                        )
                      : const Icon(Icons.send_rounded,
                          color: Color(0xFF061417), size: 20),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Animated Thinking Dots ───────────────────────────────────────────────────

class _ThinkingDots extends StatefulWidget {
  const _ThinkingDots();

  @override
  State<_ThinkingDots> createState() => _ThinkingDotsState();
}

class _ThinkingDotsState extends State<_ThinkingDots>
    with TickerProviderStateMixin {
  late List<AnimationController> _ctrls;
  late List<Animation<double>> _anims;

  @override
  void initState() {
    super.initState();
    _ctrls = List.generate(
        3,
        (i) => AnimationController(
            vsync: this, duration: const Duration(milliseconds: 500)));
    _anims = _ctrls
        .map((c) => Tween<double>(begin: 0.2, end: 1.0)
            .animate(CurvedAnimation(parent: c, curve: Curves.easeInOut)))
        .toList();
    for (int i = 0; i < 3; i++) {
      Future.delayed(Duration(milliseconds: i * 180), () {
        if (mounted) _ctrls[i].repeat(reverse: true);
      });
    }
  }

  @override
  void dispose() {
    for (final c in _ctrls) c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(
        3,
        (i) => AnimatedBuilder(
          animation: _anims[i],
          builder: (_, __) => Container(
            margin: const EdgeInsets.symmetric(horizontal: 3),
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: Color.fromRGBO(47, 230, 209, _anims[i].value),
              shape: BoxShape.circle,
            ),
          ),
        ),
      ),
    );
  }
}
