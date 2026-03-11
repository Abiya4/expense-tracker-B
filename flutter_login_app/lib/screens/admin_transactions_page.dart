import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';

class AdminTransactionsPage extends StatefulWidget {
  const AdminTransactionsPage({super.key});

  @override
  State<AdminTransactionsPage> createState() => _AdminTransactionsPageState();
}

class _AdminTransactionsPageState extends State<AdminTransactionsPage> {
  final String baseUrl = Constants.baseUrl;
  final TextEditingController searchController = TextEditingController();
  List<dynamic> transactions = [];
  List<dynamic> filteredTransactions = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchTransactions();
  }

  Future<void> fetchTransactions() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(Uri.parse("$baseUrl/admin/expenses"));
      if (response.statusCode == 200) {
        setState(() {
          transactions = jsonDecode(response.body);
          filteredTransactions = transactions;
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Failed to load transactions")),
      );
    }
  }

  void filterTransactions(String query) {
    if (query.isEmpty) {
      setState(() {
        filteredTransactions = transactions;
      });
    } else {
      setState(() {
        filteredTransactions = transactions.where((t) {
          final username = t['username'].toString().toLowerCase();
          return username.contains(query.toLowerCase());
        }).toList();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050B18),
      body: SafeArea(
        child: Column(
          children: [
            _header(),
            const SizedBox(height: 20),
            _searchBar(),
            const SizedBox(height: 20),
            Expanded(
              child: isLoading
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: Color(0xFF2FE6D1),
                      ),
                    )
                  : filteredTransactions.isEmpty
                      ? _emptyState()
                      : RefreshIndicator(
                          onRefresh: fetchTransactions,
                          child: ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 20),
                            itemCount: filteredTransactions.length,
                            itemBuilder: (context, index) {
                              final transaction = filteredTransactions[index];
                              return _transactionCard(transaction);
                            },
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  // ---------------- HEADER ----------------
  Widget _header() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () => Navigator.pop(context),
          ),
          const Text(
            "All Transactions",
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  // ---------------- SEARCH BAR ----------------
  Widget _searchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.06),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withOpacity(0.08)),
            ),
            child: TextField(
              controller: searchController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: "Search by username...",
                hintStyle: const TextStyle(color: Colors.white54),
                border: InputBorder.none,
                icon: const Icon(Icons.search, color: Color(0xFF2FE6D1)),
                suffixIcon: searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, color: Colors.white54),
                        onPressed: () {
                          searchController.clear();
                          filterTransactions("");
                        },
                      )
                    : null,
              ),
              onChanged: filterTransactions,
            ),
          ),
        ),
      ),
    );
  }

  // ---------------- EMPTY STATE ----------------
  Widget _emptyState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.receipt_long,
            size: 80,
            color: Colors.white24,
          ),
          SizedBox(height: 16),
          Text(
            "No transactions yet",
            style: TextStyle(
              color: Colors.white54,
              fontSize: 18,
            ),
          ),
        ],
      ),
    );
  }

  // ---------------- TRANSACTION CARD ----------------
  Widget _transactionCard(Map<String, dynamic> transaction) {
    IconData categoryIcon;
    Color categoryColor;

    switch (transaction['category']) {
      case 'Food':
        categoryIcon = Icons.restaurant;
        categoryColor = Colors.orange;
        break;
      case 'Shopping':
        categoryIcon = Icons.shopping_bag;
        categoryColor = Colors.pink;
        break;
      case 'Transport':
        categoryIcon = Icons.directions_car;
        categoryColor = Colors.blue;
        break;
      case 'Entertainment':
        categoryIcon = Icons.movie;
        categoryColor = Colors.purple;
        break;
      case 'Bills':
        categoryIcon = Icons.receipt;
        categoryColor = Colors.red;
        break;
      case 'Health':
        categoryIcon = Icons.medical_services;
        categoryColor = Colors.green;
        break;
      default:
        categoryIcon = Icons.category;
        categoryColor = Colors.grey;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.06),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withOpacity(0.08)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: categoryColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    categoryIcon,
                    color: categoryColor,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        transaction['category'],
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(
                            Icons.person_outline,
                            color: Color(0xFF2FE6D1),
                            size: 14,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            transaction['username'],
                            style: const TextStyle(
                              color: Color(0xFF2FE6D1),
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        transaction['date'],
                        style: const TextStyle(
                          color: Colors.white54,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  "₹${transaction['amount'].toStringAsFixed(2)}",
                  style: const TextStyle(
                    color: Colors.redAccent,
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}