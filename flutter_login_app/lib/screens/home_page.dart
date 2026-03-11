import 'dart:ui';
import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'add_expense_page.dart';
import 'view_expense_page.dart';
import 'insights_page.dart';
import 'ai_page.dart';
import 'wishlist_page.dart';
import '../services/sms_service.dart';
import '../services/notification_service.dart';
import '../utils/constants.dart';

class HomePage extends StatefulWidget {
  final String username;
  final int userId;

  const HomePage({super.key, required this.username, required this.userId});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with WidgetsBindingObserver {
  int _currentIndex = 0;
  double balance = 0.0;
  bool isLoading = true;
  final String baseUrl = Constants.baseUrl;
  late SmsService _smsService;
  late StreamSubscription _smsSubscription;
  String budgetInsightText = "Manage wisely";
  String savingsInsightText = "";

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    fetchBalance();
    _smsService = SmsService(context, widget.userId);
    _smsService.initListener();
    _smsSubscription = SmsService.onSmsEvent.listen((_) {
      if (mounted) fetchBalance();
    });
  }

  @override
  void dispose() {
    _smsSubscription.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _smsService.syncOfflineSms();
      fetchBalance();
    }
  }

  Future<void> fetchBalance() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(Uri.parse("$baseUrl/balance"));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          balance = (data['balance'] as num).toDouble();
          isLoading = false;
        });
        
        // Check budget every time the balance updates (e.g. on return or SMS)
        await _checkAndShowBudgetAlert();
        await fetchInsights();
      }
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Failed to load balance")),
      );
    }
  }

  Future<void> fetchInsights() async {
    try {
      final res = await http.get(Uri.parse("$baseUrl/budget/home_insights/${widget.userId}"));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          if (data['has_budget'] == true) {
            budgetInsightText = "₹${data['budget_left']} left for ${data['days_left']} days, limit to ₹${data['daily_limit']}/day";
          } else {
            budgetInsightText = "Set a budget to manage wisely";
          }
          savingsInsightText = "Savings: ${data['savings_rate']}% | MoM: ${data['suggestion']}";
        });
      }
    } catch (e) {
      debugPrint("Insights fetch error: $e");
    }
  }

  // ---------------- BUDGET ALERT CHECK ----------------
  Future<void> _checkAndShowBudgetAlert() async {
    try {
      final response = await http.get(
        Uri.parse("$baseUrl/budget/check_alert/${widget.userId}"), 
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final alert = data["alert"];
        if (alert != null) {
          NotificationService().showNotification(
            id: 1,
            title: "Budget Alert",
            body: alert.toString(),
          );
        }
      }
    } catch (e) {
      debugPrint("Alert check error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050B18),
      bottomNavigationBar: _bottomNav(),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: fetchBalance,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _header(),
                const SizedBox(height: 20),
                _balanceCard(),
                const SizedBox(height: 24),
                _actionButtons(),
                const SizedBox(height: 24),
                _quickInsights(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── HEADER ──────────────────────────────────────────────
  Widget _header() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "WELCOME,",
              style: TextStyle(color: Colors.white54, fontSize: 14),
            ),
            const SizedBox(height: 4),
            Text(
              "${widget.username} 👋",
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ],
        ),
        const SizedBox(height: 44), // To keep symmetrical spacing if needed, or simply empty.
      ],
    );
  }

  // ── BALANCE CARD ────────────────────────────────────────
  Widget _balanceCard() {
    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text("Available Balance",
              style: TextStyle(color: Colors.white54)),
          const SizedBox(height: 8),
          isLoading
              ? const CircularProgressIndicator(color: Color(0xFF2FE6D1))
              : Text(
                  "₹${balance.toStringAsFixed(2)}",
                  style: const TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w600,
                      color: Colors.white),
                ),
          const SizedBox(height: 16),
          const Text(
            "Pull down to refresh",
            style: TextStyle(color: Colors.white38, fontSize: 12),
          ),
        ],
      ),
    );
  }

  // ── ACTION BUTTONS ──────────────────────────────────────
  Widget _actionButtons() {
    return Row(
      children: [
        Expanded(
          child: _glassCard(
            child: InkWell(
              onTap: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const AddExpensePage()),
                );
                fetchBalance();
              },
              child: const Column(
                children: [
                  Icon(Icons.add_circle_outline,
                      color: Color(0xFF2FE6D1), size: 32),
                  SizedBox(height: 8),
                  Text("Add Transaction", style: TextStyle(color: Colors.white)),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _glassCard(
            child: InkWell(
              onTap: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const ViewExpensesPage()),
                );
                fetchBalance();
              },
              child: const Column(
                children: [
                  Icon(Icons.receipt_long, color: Color(0xFF2FE6D1), size: 32),
                  SizedBox(height: 8),
                  Text("View Transactions", style: TextStyle(color: Colors.white)),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ── QUICK INSIGHTS ──────────────────────────────────────
  Widget _quickInsights() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          "Quick Insights",
          style: TextStyle(
              color: Colors.white, fontSize: 18, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            // Track Spending → goes to Insights/Analytics
            Expanded(
              child: _glassCard(
                child: InkWell(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (_) => InsightsPage(userId: widget.userId)),
                    );
                  },
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.trending_up, color: Colors.green),
                      SizedBox(height: 8),
                      Text("Track Spending",
                          style: TextStyle(color: Colors.white54)),
                      SizedBox(height: 4),
                      Text("View all expenses",
                          style: TextStyle(color: Colors.white, fontSize: 12)),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Budget Control → goes to AI chatbot
            Expanded(
              child: _glassCard(
                child: InkWell(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (_) => AIPage(userId: widget.userId)),
                    );
                  },
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.wallet, color: Colors.orange),
                      const SizedBox(height: 8),
                      const Text("Budget Control",
                          style: TextStyle(color: Colors.white54)),
                      const SizedBox(height: 4),
                      Text(budgetInsightText,
                          style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
                      if (savingsInsightText.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(savingsInsightText,
                              style: const TextStyle(color: Colors.white70, fontSize: 10)),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ── GLASS CARD ──────────────────────────────────────────
  Widget _glassCard({required Widget child}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: child,
        ),
      ),
    );
  }

  // ── BOTTOM NAV ──────────────────────────────────────────
  Widget _bottomNav() {
    return BottomNavigationBar(
      currentIndex: _currentIndex,
      backgroundColor: const Color(0xFF050B18),
      type: BottomNavigationBarType.fixed,
      selectedItemColor: const Color(0xFF2FE6D1),
      unselectedItemColor: Colors.white38,
      onTap: (index) {
        if (index == 2) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const AddExpensePage()),
          ).then((_) => fetchBalance());
        } else if (index == 1) {
          Navigator.push(
            context,
            MaterialPageRoute(
                builder: (_) => InsightsPage(userId: widget.userId)),
          );
        } else if (index == 4) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => AIPage(userId: widget.userId)),
          );
        } else if (index == 3) {
          Navigator.push(
            context,
            MaterialPageRoute(
                builder: (_) => WishlistPage(userId: widget.userId)),
          );
        } else {
          setState(() => _currentIndex = index);
        }
      },
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.home), label: "Home"),
        BottomNavigationBarItem(icon: Icon(Icons.pie_chart), label: "Insights"),
        BottomNavigationBarItem(
          icon: CircleAvatar(
            radius: 22,
            backgroundColor: Color(0xFF2FE6D1),
            child: Icon(Icons.add, color: Color(0xFF061417)),
          ),
          label: "",
        ),
        BottomNavigationBarItem(
            icon: Icon(Icons.favorite_border), label: "Wishlist"),
        BottomNavigationBarItem(icon: Icon(Icons.smart_toy), label: "AI"),
      ],
    );
  }
}
