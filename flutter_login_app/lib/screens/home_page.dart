import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'add_expense_page.dart';
import 'view_expense_page.dart';
import 'insights_page.dart';
import '../services/sms_service.dart';

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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    fetchBalance();
    _smsService = SmsService(context, widget.userId, onRefresh: fetchBalance);
    _smsService.initListener();
  }

  @override
  void dispose() {
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
          balance = data['balance'].toDouble();
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Failed to load balance")),
      );
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

  // ---------------- HEADER ----------------
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
        Container(
          height: 44,
          width: 44,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white.withOpacity(0.08),
          ),
          child: const Icon(Icons.notifications_none, color: Colors.white),
        )
      ],
    );
  }

  // ---------------- BALANCE CARD ----------------
  Widget _balanceCard() {
    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text("Available Balance",
              style: TextStyle(color: Colors.white54)),
          const SizedBox(height: 8),
          isLoading
              ? const CircularProgressIndicator(
                  color: Color(0xFF2FE6D1),
                )
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

  // ---------------- ACTION BUTTONS ----------------
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
              child: Column(
                children: const [
                  Icon(Icons.add_circle_outline,
                      color: Color(0xFF2FE6D1), size: 32),
                  SizedBox(height: 8),
                  Text("Add Expense",
                      style: TextStyle(color: Colors.white)),
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
              child: Column(
                children: const [
                  Icon(Icons.receipt_long,
                      color: Color(0xFF2FE6D1), size: 32),
                  SizedBox(height: 8),
                  Text("View Expenses",
                      style: TextStyle(color: Colors.white)),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ---------------- QUICK INSIGHTS ----------------
  Widget _quickInsights() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          "Quick Insights",
          style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _glassCard(
                child: InkWell(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => InsightsPage(userId: widget.userId)),
                    );
                  },
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
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
            Expanded(
              child: _glassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Icon(Icons.wallet, color: Colors.orange),
                    SizedBox(height: 8),
                    Text("Budget Control",
                        style: TextStyle(color: Colors.white54)),
                    SizedBox(height: 4),
                    Text("Manage wisely",
                        style: TextStyle(color: Colors.white, fontSize: 12)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ---------------- GLASS CARD ----------------
  Widget _glassCard({required Widget child}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.06),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withOpacity(0.08)),
          ),
          child: child,
        ),
      ),
    );
  }

  // ---------------- BOTTOM NAV ----------------
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
            MaterialPageRoute(builder: (_) => InsightsPage(userId: widget.userId)),
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