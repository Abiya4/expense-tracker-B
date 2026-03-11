import 'dart:ui';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'login_page.dart';

import '../utils/constants.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final TextEditingController usernameController = TextEditingController();
  final TextEditingController phoneController = TextEditingController();
  final TextEditingController balanceController = TextEditingController();
  final TextEditingController passwordController = TextEditingController();

  Future<void> registerUser() async {
    final name = usernameController.text.trim();
    final phone = phoneController.text.trim();

    if (name.isEmpty || !RegExp(r'^[a-zA-Z\s]+$').hasMatch(name)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Name must contain only letters and spaces."),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    if (phone.isEmpty || !RegExp(r'^\d{10}$').hasMatch(phone)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Phone number must be exactly 10 digits."),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    try {
      final response = await http.post(
        Uri.parse("${Constants.baseUrl}/signup"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "username": name,
          "phone": phone,
          "password": passwordController.text.trim(),
          "balance": double.tryParse(balanceController.text) ?? 0,
        }),
      );

      final data = jsonDecode(response.body);

      if (response.statusCode == 201 && data["success"] == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Registration successful. Please login."),
            backgroundColor: Colors.green,
          ),
        );

        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const LoginPage()),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(data["message"] ?? "Registration failed"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Cannot connect to server"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF050B18), Color(0xFF0B1E2D)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                  child: Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.05),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: Colors.white.withOpacity(0.1)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          "Create Account",
                          style: TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.w500,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          "Track your money smarter",
                          style: TextStyle(fontSize: 14, color: Colors.white70),
                        ),
                        const SizedBox(height: 28),

                        _inputField(
                          "Username",
                          Icons.person_outline,
                          controller: usernameController,
                        ),
                        const SizedBox(height: 18),
                        _inputField(
                          "Phone Number",
                          Icons.phone_outlined,
                          keyboard: TextInputType.phone,
                          controller: phoneController,
                        ),
                        const SizedBox(height: 18),
                        _inputField(
                          "Initial Balance",
                          Icons.account_balance_wallet_outlined,
                          keyboard: TextInputType.number,
                          controller: balanceController,
                        ),
                        const SizedBox(height: 18),
                        _inputField(
                          "Password",
                          Icons.lock_outline,
                          obscure: true,
                          controller: passwordController,
                        ),

                        const SizedBox(height: 30),
                        SizedBox(
                          width: double.infinity,
                          height: 54,
                          child: ElevatedButton(
                            onPressed: registerUser,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF2FE6D1),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                            child: const Text(
                              "Register",
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                                color: Color(0xFF061417),
                              ),
                            ),
                          ),
                        ),

                        const SizedBox(height: 18),
                        Center(
                          child: GestureDetector(
                            onTap: () {
                              Navigator.pushReplacement(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => const LoginPage(),
                                ),
                              );
                            },
                            child: const Text(
                              "Already registered? Login",
                              style: TextStyle(
                                color: Color(0xFF2FE6D1),
                                fontSize: 14,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static Widget _inputField(
    String hint,
    IconData icon, {
    TextInputType keyboard = TextInputType.text,
    bool obscure = false,
    required TextEditingController controller,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: TextField(
        controller: controller,
        keyboardType: keyboard,
        obscureText: obscure,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: const TextStyle(color: Colors.white54),
          prefixIcon: Icon(icon, color: const Color(0xFF2FE6D1)),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(
            vertical: 18,
            horizontal: 16,
          ),
        ),
      ),
    );
  }
}