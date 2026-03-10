import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'admin_users_page.dart';
import 'admin_transactions_page.dart';
import 'login_page.dart';

class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key});

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  final String baseUrl = "http://10.0.5.13:5000";
  
  int totalUsers = 0;
  double totalExpenses = 0.0;
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchAnalytics();
  }

  Future<void> fetchAnalytics() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(Uri.parse("$baseUrl/admin/analytics"));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          totalUsers = data['total_users'];
          totalExpenses = data['total_expenses'].toDouble();
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Failed to load analytics")),
      );
    }
  }

  Future<void> logout() async {
    try {
      await http.post(Uri.parse("$baseUrl/logout"));
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const LoginPage()),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Logout failed")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050B18),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: fetchAnalytics,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _header(),
                const SizedBox(height: 24),
                _analyticsCards(),
                const SizedBox(height: 24),
                _actionButtons(),
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
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "ADMIN PANEL",
              style: TextStyle(color: Colors.white54, fontSize: 14),
            ),
            SizedBox(height: 4),
            Text(
              "Dashboard 📊",
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ],
        ),
        IconButton(
          icon: const Icon(Icons.logout, color: Colors.white),
          onPressed: logout,
        ),
      ],
    );
  }

  // ---------------- ANALYTICS CARDS ----------------
  Widget _analyticsCards() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _glassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.people, color: Color(0xFF2FE6D1), size: 32),
                    const SizedBox(height: 12),
                    const Text(
                      "Total Users",
                      style: TextStyle(color: Colors.white54, fontSize: 14),
                    ),
                    const SizedBox(height: 4),
                    isLoading
                        ? const CircularProgressIndicator(
                            color: Color(0xFF2FE6D1),
                          )
                        : Text(
                            "$totalUsers",
                            style: const TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _glassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.money_off, color: Colors.redAccent, size: 32),
                    const SizedBox(height: 12),
                    const Text(
                      "Total Expenses",
                      style: TextStyle(color: Colors.white54, fontSize: 14),
                    ),
                    const SizedBox(height: 4),
                    isLoading
                        ? const CircularProgressIndicator(
                            color: Color(0xFF2FE6D1),
                          )
                        : Text(
                            "₹${totalExpenses.toStringAsFixed(2)}",
                            style: const TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ---------------- ACTION BUTTONS ----------------
  Widget _actionButtons() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          "Quick Actions",
          style: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 12),
        _glassCard(
          child: InkWell(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AdminUsersPage()),
              ).then((_) => fetchAnalytics());
            },
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Row(
                children: [
                  Icon(Icons.people_outline, color: Color(0xFF2FE6D1), size: 28),
                  SizedBox(width: 16),
                  Expanded(
                    child: Text(
                      "Manage Users",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  Icon(Icons.arrow_forward_ios, color: Colors.white54, size: 18),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        _glassCard(
          child: InkWell(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AdminTransactionsPage()),
              );
            },
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Row(
                children: [
                  Icon(Icons.receipt_long, color: Color(0xFF2FE6D1), size: 28),
                  SizedBox(width: 16),
                  Expanded(
                    child: Text(
                      "View All Transactions",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  Icon(Icons.arrow_forward_ios, color: Colors.white54, size: 18),
                ],
              ),
            ),
          ),
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
}
