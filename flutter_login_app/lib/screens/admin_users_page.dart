import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';

class AdminUsersPage extends StatefulWidget {
  const AdminUsersPage({super.key});

  @override
  State<AdminUsersPage> createState() => _AdminUsersPageState();
}

class _AdminUsersPageState extends State<AdminUsersPage> {
  final String baseUrl = Constants.baseUrl;
  final TextEditingController searchController = TextEditingController();
  List<dynamic> users = [];
  List<dynamic> filteredUsers = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchUsers();
  }

  Future<void> fetchUsers([String query = '']) async {
    setState(() => isLoading = true);
    try {
      final url = query.isEmpty
          ? "$baseUrl/admin/users"
          : "$baseUrl/admin/users?q=$query";
      
      final response = await http.get(Uri.parse(url));
      if (response.statusCode == 200) {
        setState(() {
          users = jsonDecode(response.body);
          filteredUsers = users;
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Failed to load users")),
      );
    }
  }

  Future<void> deleteUser(int userId, String username) async {
    try {
      final response = await http.delete(
        Uri.parse("$baseUrl/admin/users/$userId"),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("User '$username' removed successfully"),
            backgroundColor: Colors.green,
          ),
        );
        fetchUsers(); // Refresh list
      } else {
        final data = jsonDecode(response.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(data["message"] ?? "Failed to delete user"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Error deleting user"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void showDeleteConfirmation(int userId, String username) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF0B1E2D),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: const Text(
          "Remove User?",
          style: TextStyle(color: Colors.white),
        ),
        content: Text(
          "Are you sure you want to remove user '$username'? This will delete all their data permanently.",
          style: const TextStyle(color: Colors.white70),
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
              deleteUser(userId, username);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: const Text("Remove"),
          ),
        ],
      ),
    );
  }

  void showUserDetails(Map<String, dynamic> user) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF0B1E2D),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: Text(
          user['username'],
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _detailRow(Icons.phone, "Phone", user['phone']),
            const SizedBox(height: 12),
            _detailRow(Icons.account_balance_wallet, "Balance", "₹${user['balance'].toStringAsFixed(2)}"),
            const SizedBox(height: 12),
            _detailRow(Icons.star, "Top Category", user['top_category'] ?? "No expenses"),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Close", style: TextStyle(color: Color(0xFF2FE6D1))),
          ),
        ],
      ),
    );
  }

  Widget _detailRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, color: Colors.white54, size: 20),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
            Text(value, style: const TextStyle(color: Colors.white, fontSize: 16)),
          ],
        ),
      ],
    );
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
                  : filteredUsers.isEmpty
                      ? _emptyState()
                      : RefreshIndicator(
                          onRefresh: () => fetchUsers(),
                          child: ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 20),
                            itemCount: filteredUsers.length,
                            itemBuilder: (context, index) {
                              final user = filteredUsers[index];
                              return _userCard(user);
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
            "Manage Users",
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
                hintText: "Search by username or phone...",
                hintStyle: const TextStyle(color: Colors.white54),
                border: InputBorder.none,
                icon: const Icon(Icons.search, color: Color(0xFF2FE6D1)),
                suffixIcon: searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, color: Colors.white54),
                        onPressed: () {
                          searchController.clear();
                          fetchUsers();
                        },
                      )
                    : null,
              ),
              onChanged: (value) {
                if (value.isEmpty) {
                  fetchUsers();
                } else {
                  fetchUsers(value);
                }
              },
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
            Icons.people_outline,
            size: 80,
            color: Colors.white24,
          ),
          SizedBox(height: 16),
          Text(
            "No users found",
            style: TextStyle(
              color: Colors.white54,
              fontSize: 18,
            ),
          ),
        ],
      ),
    );
  }

  // ---------------- USER CARD ----------------
  Widget _userCard(Map<String, dynamic> user) {
    final bool isActive = user['active'];

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => showUserDetails(user),
        borderRadius: BorderRadius.circular(16),
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
                    color: const Color(0xFF2FE6D1).withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.person,
                    color: Color(0xFF2FE6D1),
                    size: 28,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user['username'],
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
                            Icons.phone,
                            color: Colors.white54,
                            size: 14,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            user['phone'],
                            style: const TextStyle(
                              color: Colors.white54,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: isActive
                                  ? Colors.green.withOpacity(0.2)
                                  : Colors.red.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              isActive ? "Active" : "Inactive",
                              style: TextStyle(
                                color: isActive ? Colors.green : Colors.red,
                                fontSize: 11,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            "₹${user['balance'].toStringAsFixed(2)}",
                            style: const TextStyle(
                              color: Color(0xFF2FE6D1),
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Column(
                  children: [
                    Text(
                      "ID: ${user['id']}",
                      style: const TextStyle(
                        color: Colors.white54,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: () => showDeleteConfirmation(
                        user['id'],
                        user['username'],
                      ),
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.delete_outline,
                          color: Colors.red,
                          size: 20,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
      ),
    );
  }
}