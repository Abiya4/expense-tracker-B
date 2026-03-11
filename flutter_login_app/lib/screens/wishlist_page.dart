import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';
import '../services/notification_service.dart';

class WishlistPage extends StatefulWidget {
  final int userId;
  const WishlistPage({super.key, required this.userId});

  @override
  State<WishlistPage> createState() => _WishlistPageState();
}

class _WishlistPageState extends State<WishlistPage> {
  final String baseUrl = Constants.baseUrl;

  // controllers
  final TextEditingController budgetController = TextEditingController();
  final TextEditingController itemController = TextEditingController();
  final TextEditingController amountController = TextEditingController();
  final TextEditingController saveAmountController = TextEditingController();

  //String selectedCategory = "General";

  List wishlist = [];
  double budgetProgress = 0.0;
  double totalExpense = 0.0;
  double monthlyLimit = 0.0;

  //new stuff
  double actualBalance = 0.0;
  double savedAmount = 0.0;
  double spendableBalance = 0.0;

  @override
  void initState() {
    super.initState();
    fetchWishlist();
    fetchBudgetProgress();
    fetchBalances();
  }

  Future<void> fetchWishlist() async {
    try {
      final response =
          await http.get(Uri.parse("$baseUrl/wishlist/${widget.userId}"));
      if (response.statusCode == 200) {
        setState(() {
          wishlist = jsonDecode(response.body);
        });
      }
    } catch (e) {
      debugPrint("Wishlist fetch error: $e");
    }
  }

  Future<void> fetchBudgetProgress() async {
    try {
      final response = await http
          .get(Uri.parse("$baseUrl/budget/progress/${widget.userId}"));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          budgetProgress = (data["progress"] ?? 0).toDouble();
          totalExpense = (data["total_expense"] ?? 0).toDouble();
          monthlyLimit = (data["monthly_limit"] ?? 0).toDouble();
        });
      }
    } catch (e) {
      debugPrint("Budget progress error: $e");
    }
  }

  Future<void> fetchBalances() async {
    try {
      final response =
          await http.get(Uri.parse("$baseUrl/balances/${widget.userId}"));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          actualBalance = (data["actual_balance"] ?? 0).toDouble();
          savedAmount = (data["saved_amount"] ?? 0).toDouble();
          spendableBalance = (data["spendable_balance"] ?? 0).toDouble();
        });
      }
    } catch (e) {
      debugPrint("Balances fetch error: $e");
    }
  }

  Future<void> addWishlistItem() async {
    if (itemController.text.isEmpty || amountController.text.isEmpty) return;

    if (wishlist.length >= 7) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF161D32),
          title: const Row(
            children: [
              Icon(Icons.error_outline, color: Colors.redAccent),
              SizedBox(width: 8),
              Text("Limit Reached", style: TextStyle(color: Colors.white)),
            ],
          ),
          content: const Text(
            "You can only have up to 7 wishlist items at a time. Please delete an item before adding a new one.",
            style: TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text("OK", style: TextStyle(color: Color(0xFF2FE6D1))),
            ),
          ],
        ),
      );
      return;
    }

    try {
      final response = await http.post(
        Uri.parse("$baseUrl/wishlist"), // fixed: was /wishlist/add
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "user_id": widget.userId,
          "item_name": itemController.text,
          "target_amount": double.parse(amountController.text),
          // removed: target_months, category
        }),
      );

      if (response.statusCode == 201) {
        itemController.clear();
        amountController.clear();
        await fetchWishlist();
        await fetchBalances();
      } else {
        _showSnack("Failed to add item", isError: true);
      }
    } catch (e) {
      debugPrint("Add wishlist error: $e");
    }
  }

  Future<void> saveMoney(int wishlistId) async {
    if (saveAmountController.text.isEmpty) return;

    final double amount = double.tryParse(saveAmountController.text) ?? 0;
    if (amount <= 0) return;

    try {
      final response = await http.post(
        Uri.parse("$baseUrl/wishlist/save"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "user_id": widget.userId,
          "wishlist_id": wishlistId,
          "amount": amount,
        }),
      );

      saveAmountController.clear();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // show reset warning if triggered
        if (data["reset_triggered"] == true && mounted) {
          _showSnack(
            "⚠ Spendable balance went below zero — all wishlist savings have been reset.",
            isError: true,
            duration: 5,
          );
        }

        await fetchWishlist();
        await fetchBalances();
      } else {
        final data = jsonDecode(response.body);
        _showSnack(data["message"] ?? "Failed to save", isError: true);
      }
    } catch (e) {
      debugPrint("Save money error: $e");
    }
  }

  Future<void> setBudget() async {
    if (budgetController.text.isEmpty) return;
    
    final double? parsedLimit = double.tryParse(budgetController.text);
    if (parsedLimit == null || parsedLimit <= 0) {
      _showSnack("Budget limit must be greater than 0", isError: true);
      return;
    }

    try {
      await http.post(
        Uri.parse("$baseUrl/budget/set"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "user_id": widget.userId,
          "monthly_limit": parsedLimit,
        }),
      );

      budgetController.clear();
      await fetchBudgetProgress();
      await _checkAndShowBudgetAlert();
    } catch (e) {
      debugPrint("Budget set error: $e");
    }
  }

  Future<void> _checkAndShowBudgetAlert() async {
    try {
      final response = await http.get(
        Uri.parse("$baseUrl/budget/check_alert/${widget.userId}"),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final alert = data["alert"];
        if (alert != null && mounted) {
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

  void _showSnack(String message, {bool isError = false, int duration = 3}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.redAccent : const Color(0xFF2FE6D1),
        duration: Duration(seconds: duration),
      ),
    );
  }

  void showBudgetDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF0E1625),
        title: const Text("Set Monthly Budget",
            style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: budgetController,
          keyboardType: TextInputType.number,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: "Enter amount",
            hintStyle: TextStyle(color: Colors.white38),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context); // pop first
              await setBudget(); // then await
            },
            child: const Text("Save"),
          ),
        ],
      ),
    );
  }

  void showSaveDialog(int wishlistId) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF0E1625),
        title:
            const Text("Add to Savings", style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Spendable balance: ₹${spendableBalance.toStringAsFixed(2)}",
              style: const TextStyle(color: Colors.white54, fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: saveAmountController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                hintText: "Amount to save",
                hintStyle: TextStyle(color: Colors.white38),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context); // pop first
              await saveMoney(wishlistId); // then await
            },
            child: const Text("Save"),
          ),
        ],
      ),
    );
  }

  Future<void> deleteWishlistItem(int wishlistId) async {
    try {
      final response = await http.delete(
        Uri.parse("$baseUrl/wishlist/$wishlistId"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "user_id": widget.userId,
        }),
      );

      if (response.statusCode == 200) {
        _showSnack("Wishlist item deleted successfully");
        await fetchWishlist();
        await fetchBalances();
      } else {
        final data = jsonDecode(response.body);
        _showSnack(data["message"] ?? "Failed to delete item", isError: true);
      }
    } catch (e) {
      debugPrint("Delete wishlist error: $e");
    }
  }

  void showDeleteDialog(int wishlistId) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF0E1625),
        title: const Text("Delete Wishlist Item",
            style: TextStyle(color: Colors.white)),
        content: const Text(
          "Are you sure you want to permanently delete this item? All savings progress will be lost.",
          style: TextStyle(color: Colors.white54, fontSize: 14),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await deleteWishlistItem(wishlistId);
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text("Delete", style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  Future<void> dismissRecovery(int wishlistId) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/wishlist/dismiss_recovery"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "user_id": widget.userId,
          "wishlist_id": wishlistId,
        }),
      );

      if (response.statusCode == 200) {
        await fetchWishlist();
      }
    } catch (e) {
      debugPrint("Dismiss recovery error: $e");
    }
  }

  void showRestoreDialog(int wishlistId, double previousSaved) {
    final TextEditingController restoreController =
        TextEditingController(text: previousSaved.toStringAsFixed(0));

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF0E1625),
        title: const Text("Restore Savings",
            style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Your progress was recently reset because your balance dropped.",
              style: TextStyle(color: Colors.redAccent, fontSize: 13),
            ),
            const SizedBox(height: 8),
            Text(
              "Spendable balance: ₹${spendableBalance.toStringAsFixed(2)}",
              style: const TextStyle(color: Colors.white54, fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: restoreController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                hintText: "Amount to restore",
                hintStyle: TextStyle(color: Colors.white38),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              dismissRecovery(wishlistId);
            },
            child: const Text("Dismiss",
                style: TextStyle(color: Colors.redAccent)),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              saveAmountController.text = restoreController.text;
              await saveMoney(wishlistId);
            },
            style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF2FE6D1)),
            child: const Text("Restore", style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050B18),
      appBar: AppBar(
        backgroundColor: const Color(0xFF050B18),
        title: const Text("Wishlist & Budget",
            style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await fetchWishlist();
          await fetchBudgetProgress();
          await fetchBalances();
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                _budgetProgressCard(),
                const SizedBox(height: 16),
                _balanceCard(),
                const SizedBox(height: 16),
                _addGoalCard(),
                const SizedBox(height: 16),
                _wishlistList(), // no SizedBox wrapper — grows naturally
              ],
            ),
          ),
        ),
      ),
    );
  }

// ─────────────────────────────────────────────
  //  WIDGETS
  // ─────────────────────────────────────────────

  Widget _budgetProgressCard() {
    Color progressColor =
        budgetProgress >= 0.75 ? Colors.red : const Color(0xFF2FE6D1);

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                "Monthly Budget",
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold),
              ),
              IconButton(
                icon: const Icon(Icons.edit, color: Color(0xFF2FE6D1)),
                onPressed: showBudgetDialog,
              ),
            ],
          ),
          const SizedBox(height: 12),
          LinearProgressIndicator(
            value: budgetProgress,
            backgroundColor: Colors.white12,
            color: progressColor,
            minHeight: 10,
          ),
          const SizedBox(height: 8),
          Text(
            "₹${totalExpense.toStringAsFixed(0)} / ₹${monthlyLimit.toStringAsFixed(0)}",
            style: const TextStyle(color: Colors.white54),
          ),
        ],
      ),
    );
  }

  Widget _balanceCard() {
    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            "Balances",
            style: TextStyle(
                color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          _balanceRow("Actual Balance", "₹${actualBalance.toStringAsFixed(2)}",
              Colors.white),
          const SizedBox(height: 6),
          _balanceRow("Saved (Wishlist)", "₹${savedAmount.toStringAsFixed(2)}",
              Colors.white70),
          const Divider(color: Colors.white12, height: 20),
          _balanceRow(
            "Spendable Balance",
            "₹${spendableBalance.toStringAsFixed(2)}",
            spendableBalance < 0 ? Colors.redAccent : const Color(0xFF2FE6D1),
            bold: true,
          ),
        ],
      ),
    );
  }

  Widget _balanceRow(String label, String value, Color valueColor,
      {bool bold = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label,
            style: const TextStyle(color: Colors.white54, fontSize: 14)),
        Text(value,
            style: TextStyle(
              color: valueColor,
              fontSize: 14,
              fontWeight: bold ? FontWeight.bold : FontWeight.normal,
            )),
      ],
    );
  }

  Widget _addGoalCard() {
    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            "Add Wishlist Item",
            style: TextStyle(
                color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          // fixed: item name uses text keyboard
          _inputField(itemController, "Item Name",
              keyboardType: TextInputType.text),
          const SizedBox(height: 12),
          _inputField(amountController, "Target Amount",
              keyboardType: TextInputType.number),
          // removed: months field, category dropdown
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF2FE6D1),
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: addWishlistItem,
              child: const Text("Add to Wishlist",
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _wishlistList() {
    if (wishlist.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 40),
        child: Center(
          child: Text(
            "No wishlist items yet.\nAdd one above!",
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white38),
          ),
        ),
      );
    }

    // fixed: shrinkWrap instead of fixed SizedBox height
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: wishlist.length,
      itemBuilder: (context, index) {
        final item = wishlist[index];

        // fixed: key is total_saved (not saved_amount)
        double saved = double.tryParse(item["total_saved"].toString()) ?? 0.0;
        double target =
            double.tryParse(item["target_amount"].toString()) ?? 0.0;
        double previousSaved =
            double.tryParse(item["previous_saved"]?.toString() ?? "0") ?? 0.0;
        double progress = (target > 0 ? saved / target : 0.0).clamp(0.0, 1.0);
        bool completed = saved >= target && target > 0;

        Color barColor = completed
            ? Colors.green
            : progress >= 0.75
                ? Colors.orange
                : const Color(0xFF2FE6D1);

        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: _glassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (previousSaved > 0) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    margin: const EdgeInsets.only(bottom: 12),
                    decoration: BoxDecoration(
                      color: Colors.redAccent.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                      border:
                          Border.all(color: Colors.redAccent.withOpacity(0.3)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        const Icon(Icons.warning_amber_rounded,
                            color: Colors.redAccent, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            "You lost ₹${previousSaved.toStringAsFixed(0)} due to low balance.",
                            style: const TextStyle(
                                color: Colors.redAccent, fontSize: 12),
                          ),
                        ),
                        TextButton(
                          onPressed: () =>
                              showRestoreDialog(item["id"], previousSaved),
                          style: TextButton.styleFrom(
                            backgroundColor: Colors.redAccent.withOpacity(0.2),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            minimumSize: Size.zero,
                          ),
                          child: const Text("Restore",
                              style:
                                  TextStyle(color: Colors.white, fontSize: 12)),
                        )
                      ],
                    ),
                  ),
                ],
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        item["item_name"] ?? "",
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      "${(progress * 100).toStringAsFixed(0)}%",
                      style: TextStyle(color: barColor, fontSize: 14, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(width: 4),
                    IconButton(
                      icon: const Icon(Icons.delete_outline,
                          color: Colors.white54, size: 20),
                      onPressed: () => showDeleteDialog(item["id"]),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: progress,
                  backgroundColor: Colors.white12,
                  color: barColor,
                  minHeight: 6,
                  borderRadius: BorderRadius.circular(3),
                ),
                const SizedBox(height: 10),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      "₹${saved.toStringAsFixed(0)} / ₹${target.toStringAsFixed(0)}",
                      style: const TextStyle(color: Colors.white54, fontSize: 13),
                    ),
                    if (completed)
                      Row(
                        children: const [
                          Icon(Icons.check_circle, color: Colors.green, size: 16),
                          SizedBox(width: 4),
                          Text(
                            "Goal Completed!",
                            style: TextStyle(
                                color: Colors.green,
                                fontWeight: FontWeight.bold,
                                fontSize: 13),
                          ),
                        ],
                      )
                    else
                      SizedBox(
                        height: 32,
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.white.withOpacity(0.08),
                            foregroundColor: const Color(0xFF2FE6D1),
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8)),
                          ),
                          onPressed: () => showSaveDialog(item["id"]),
                          child: const Text("+ Save", style: TextStyle(fontSize: 13)),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ─────────────────────────────────────────────
  //  HELPERS
  // ─────────────────────────────────────────────

  Widget _inputField(
    TextEditingController controller,
    String hint, {
    TextInputType keyboardType = TextInputType.text, // fixed: was always number
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      decoration: _inputDecoration(hint),
    );
  }

  InputDecoration _inputDecoration(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: Colors.white38),
      enabledBorder: OutlineInputBorder(
        borderSide: BorderSide(color: Colors.white.withOpacity(0.2)),
        borderRadius: BorderRadius.circular(12),
      ),
      focusedBorder: const OutlineInputBorder(
        borderSide: BorderSide(color: Color(0xFF2FE6D1)),
        borderRadius: BorderRadius.all(Radius.circular(12)),
      ),
    );
  }

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
