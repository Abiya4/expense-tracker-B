import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../utils/constants.dart';

class ViewExpensesPage extends StatefulWidget {
  const ViewExpensesPage({super.key});

  @override
  State<ViewExpensesPage> createState() => _ViewExpensesPageState();
}

class _ViewExpensesPageState extends State<ViewExpensesPage> with WidgetsBindingObserver {
  List<dynamic> pendingTransactions = [];
  List<dynamic> confirmedTransactions = [];
  bool isLoading = true;
  final String baseUrl = Constants.baseUrl;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    fetchTransactions();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      // Give the system 1 second to perform cross-component SMS syncing before refreshing UI.
      Future.delayed(const Duration(seconds: 1), () {
        if (mounted) fetchTransactions();
      });
    }
  }

  Future<void> fetchTransactions() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(Uri.parse("$baseUrl/expenses"));
      if (response.statusCode == 200) {
        final List<dynamic> allTransactions = jsonDecode(response.body);
        setState(() {
          pendingTransactions = allTransactions
              .where((t) => t['status'] == 'pending')
              .toList();
          confirmedTransactions = allTransactions
              .where((t) => t['status'] != 'pending') // specific or null (legacy)
              .toList();
          isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Failed to load transactions")),
        );
      }
    }
  }

  Future<void> deleteTransaction(int id) async {
    try {
      final response = await http.delete(
        Uri.parse("$baseUrl/expenses/$id"),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Transaction deleted successfully"),
            backgroundColor: Colors.green,
          ),
        );
        fetchTransactions();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Failed to delete transaction"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Error deleting transaction"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> confirmTransaction(int id, double amount, String category, String type) async {
    try {
      final response = await http.put(
        Uri.parse("$baseUrl/expenses/$id"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "amount": amount,
          "category": category,
          "type": type,
          "status": "confirmed"
        }),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Transaction confirmed!"),
            backgroundColor: Colors.green,
          ),
        );
        fetchTransactions();
      } else {
        throw Exception("Failed to confirm");
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Error confirming transaction"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void showEditDialog(Map<String, dynamic> transaction, {bool isConfirmation = false}) {
    final amountController =
        TextEditingController(text: transaction['amount'].toString());
    String selectedCategory = transaction['category'];
    if (selectedCategory == "Uncategorized" || selectedCategory == "Unknown") {
       selectedCategory = "Food"; // Default to Food if uncategorized
    }
    String selectedType = transaction['type'];

    final expenseCategories = [
      "Food",
      "Shopping",
      "Transport",
      "Entertainment",
      "Bills",
      "Health",
      "Other",
    ];

    final incomeCategories = [
      "Salary",
      "Freelance",
      "Business",
      "Investment",
      "Gift",
      "Other",
    ];

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) {
          final categories =
              selectedType == "expense" ? expenseCategories : incomeCategories;

          // Ensure selectedCategory is in the list
          if (!categories.contains(selectedCategory)) {
             selectedCategory = categories[0];
          }

          return AlertDialog(
            backgroundColor: const Color(0xFF0B1E2D),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
            title: Text(
              isConfirmation ? "Confirm Transaction" : "Edit Transaction",
              style: const TextStyle(color: Colors.white),
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (isConfirmation) ...[
                   /* Merchant display removed */
                ],
                // Type Toggle
                Row(
                  children: [
                    Expanded(
                      child: GestureDetector(
                        onTap: () {
                          setDialogState(() {
                            selectedType = "expense";
                            selectedCategory = expenseCategories[0];
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          decoration: BoxDecoration(
                            color: selectedType == "expense"
                                ? Colors.red.withOpacity(0.3)
                                : Colors.transparent,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: selectedType == "expense"
                                  ? Colors.red
                                  : Colors.white30,
                            ),
                          ),
                          child: Text(
                            "Expense",
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: selectedType == "expense"
                                  ? Colors.red
                                  : Colors.white54,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: GestureDetector(
                        onTap: () {
                          setDialogState(() {
                            selectedType = "income";
                            selectedCategory = incomeCategories[0];
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          decoration: BoxDecoration(
                            color: selectedType == "income"
                                ? Colors.green.withOpacity(0.3)
                                : Colors.transparent,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: selectedType == "income"
                                  ? Colors.green
                                  : Colors.white30,
                            ),
                          ),
                          child: Text(
                            "Income",
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: selectedType == "income"
                                  ? Colors.green
                                  : Colors.white54,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: amountController,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: "Amount",
                    labelStyle: const TextStyle(color: Colors.white54),
                    enabledBorder: OutlineInputBorder(
                      borderSide:
                          BorderSide(color: Colors.white.withOpacity(0.3)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: const BorderSide(color: Color(0xFF2FE6D1)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  value: selectedCategory,
                  dropdownColor: const Color(0xFF0B1E2D),
                  decoration: InputDecoration(
                    labelText: "Category",
                    labelStyle: const TextStyle(color: Colors.white54),
                    enabledBorder: OutlineInputBorder(
                      borderSide:
                          BorderSide(color: Colors.white.withOpacity(0.3)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: const BorderSide(color: Color(0xFF2FE6D1)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  items: categories
                      .map((cat) => DropdownMenuItem(
                            value: cat,
                            child: Text(
                              cat,
                              style: const TextStyle(color: Colors.white),
                            ),
                          ))
                      .toList(),
                  onChanged: (val) {
                    setDialogState(() => selectedCategory = val!);
                  },
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () {
                  if (isConfirmation) {
                    deleteTransaction(transaction['id']);
                  }
                  Navigator.pop(context);
                },
                child: const Text(
                  "Cancel",
                  style: TextStyle(color: Colors.white54),
                ),
              ),
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  if (isConfirmation) {
                      confirmTransaction(
                          transaction['id'],
                          double.parse(amountController.text),
                          selectedCategory,
                          selectedType
                      );
                  } else {
                      _updateTransaction(transaction['id'], double.parse(amountController.text), selectedCategory, selectedType, transaction['status']);
                  }
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF2FE6D1),
                ),
                child: Text(isConfirmation ? "Confirm" : "Update"),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _updateTransaction(int id, double amount, String category, String type, String currentStatus) async {
       try {
        final response = await http.put(
          Uri.parse("$baseUrl/expenses/$id"),
          headers: {"Content-Type": "application/json"},
          body: jsonEncode({
            "amount": amount,
            "category": category,
            "type": type,
          }),
        );
        if (response.statusCode == 200) {
           fetchTransactions();
           ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Updated!"), backgroundColor: Colors.green));
        } else {
           ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Failed update"), backgroundColor: Colors.red));
        }
       } catch(e) {
           // Error handling
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
            const SizedBox(height: 10),
            Expanded(
              child: isLoading
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: Color(0xFF2FE6D1),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: fetchTransactions,
                      child: ListView(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        children: [
                           if (pendingTransactions.isNotEmpty) ...[
                               const Text(
                                   "PENDING ACTIONS",
                                   style: TextStyle(
                                       color: Colors.orangeAccent, 
                                       fontWeight: FontWeight.bold, 
                                       letterSpacing: 1.2
                                   ),
                               ),
                               const SizedBox(height: 10),
                               ...pendingTransactions.map((t) => _pendingTransactionCard(t)).toList(),
                               const SizedBox(height: 20),
                               const Divider(color: Colors.white24),
                               const SizedBox(height: 10),
                           ],
                           
                           if (confirmedTransactions.isNotEmpty) ...[
                               const Text(
                                   "HISTORY",
                                   style: TextStyle(
                                       color: Colors.white54, 
                                       fontWeight: FontWeight.bold,
                                       letterSpacing: 1.2
                                   ),
                               ),
                               const SizedBox(height: 10),
                               ...confirmedTransactions.map((t) => _transactionCard(t)).toList(),
                           ],
                           
                           if (pendingTransactions.isEmpty && confirmedTransactions.isEmpty)
                               SizedBox(height: 400, child: _emptyState()),
                        ],
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
            "Transactions",
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

  // ---------------- EMPTY STATE ----------------
  Widget _emptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
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

  // ---------------- VISUAL CARDS ----------------
  
  Widget _pendingTransactionCard(Map<String, dynamic> transaction) {
      return Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
              border: Border.all(color: Colors.orangeAccent.withOpacity(0.5)),
              borderRadius: BorderRadius.circular(16),
              color: Colors.orange.withOpacity(0.05),
          ),
          child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              leading: const CircleAvatar(
                  backgroundColor: Colors.orangeAccent,
                  child: Icon(Icons.priority_high, color: Colors.black),
              ),
              title: Text(
                  "Pending: ${transaction['category']}", // This likely holds merchant info from backend sync
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              subtitle: Text(
                  "${transaction['date']} • ₹${transaction['amount']}",
                  style: const TextStyle(color: Colors.white70),
              ),
              trailing: ElevatedButton(
                  onPressed: () => showEditDialog(transaction, isConfirmation: true),
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.orangeAccent),
                  child: const Text("Verify", style: TextStyle(color: Colors.black)),
              ),
          ),
      );
  }

  Widget _transactionCard(Map<String, dynamic> transaction) {
    final bool isIncome = transaction['type'] == 'income';
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
        categoryColor = Colors.teal;
        break;
      case 'Salary':
      case 'Freelance':
      case 'Business':
      case 'Investment':
      case 'Gift':
        categoryIcon = Icons.attach_money;
        categoryColor = Colors.green;
        break;
      default:
        categoryIcon = Icons.category;
        categoryColor = isIncome ? Colors.green : Colors.grey;
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
                      Row(
                        children: [
                          Text(
                            transaction['category'],
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: isIncome
                                  ? Colors.green.withOpacity(0.2)
                                  : Colors.red.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              isIncome ? "Income" : "Expense",
                              style: TextStyle(
                                color: isIncome ? Colors.green : Colors.red,
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "${transaction['date']} • ${transaction['time']}",
                        style: const TextStyle(
                          color: Colors.white54,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      "${isIncome ? '+' : '-'}₹${transaction['amount'].toStringAsFixed(2)}",
                      style: TextStyle(
                        color: isIncome ? Colors.green : Colors.redAccent,
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        InkWell(
                          onTap: () => showEditDialog(transaction),
                          child: Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(
                              color: Colors.blue.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.edit,
                              color: Colors.blue,
                              size: 16,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        InkWell(
                          onTap: () {
                            showDialog(
                              context: context,
                              builder: (context) => AlertDialog(
                                backgroundColor: const Color(0xFF0B1E2D),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                title: const Text(
                                  "Delete Transaction?",
                                  style: TextStyle(color: Colors.white),
                                ),
                                content: const Text(
                                  "This action cannot be undone.",
                                  style: TextStyle(color: Colors.white54),
                                ),
                                actions: [
                                  TextButton(
                                    onPressed: () => Navigator.pop(context),
                                    child: const Text(
                                      "Cancel",
                                      style: TextStyle(color: Colors.white54),
                                    ),
                                  ),
                                  ElevatedButton(
                                    onPressed: () {
                                      Navigator.pop(context);
                                      deleteTransaction(transaction['id']);
                                    },
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: Colors.red,
                                    ),
                                    child: const Text("Delete"),
                                  ),
                                ],
                              ),
                            );
                          },
                          child: Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(
                              color: Colors.red.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.delete,
                              color: Colors.red,
                              size: 16,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}