import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter/services.dart';


import '../utils/constants.dart';

class SMSConfirmationDialog extends StatefulWidget {
  final double amount;
  final String date;
  final String time;
  final String type; // 'income' or 'expense'
  final int userId;

  const SMSConfirmationDialog({
    Key? key,
    required this.amount,
    required this.date,
    required this.time,
    required this.type,
    required this.userId,
  }) : super(key: key);

  @override
  _SMSConfirmationDialogState createState() => _SMSConfirmationDialogState();
}

class _SMSConfirmationDialogState extends State<SMSConfirmationDialog> {
  String? _selectedCategory;
  bool _isLoading = false;

  final List<String> _expenseCategories = ['Food', 'Transport', 'Rent', 'Bills', 'Shopping', 'Entertainment', 'Health', 'Other'];
  final List<String> _incomeCategories = ['Salary', 'Freelance', 'Gift', 'Refund', 'Other'];

  Future<void> _saveTransaction() async {
    if (_selectedCategory == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please select a category')));
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final url = Uri.parse('${Constants.baseUrl}/expenses/confirm_sms');

      print("DEBUG: Sending SMS Conf Request: ${jsonEncode({
          'amount': widget.amount,
          'category': _selectedCategory,
          'type': widget.type,
          'date': widget.date,
          'time': widget.time,
          'user_id': widget.userId,
      })}");

      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'amount': widget.amount,
          'category': _selectedCategory,
          'type': widget.type,
          'date': widget.date,
          'time': _formatTimeForBackend(widget.time),
          'user_id': widget.userId,
        }),
      );

      print("DEBUG: SMS Conf Response: ${response.statusCode} - ${response.body}");

      if (response.statusCode == 201) {
        // ---> NEW: Save to native Android for the Recent notification button <---
        try {
          const platform = MethodChannel('com.example.flutter_login_app/sms_methods');
          await platform.invokeMethod('setRecentCategory', {
            'type': widget.type,
            'category': _selectedCategory,
          });
        } catch (e) {
          print("Failed to save recent category: $e");
        }

        final respData = jsonDecode(response.body);
        Navigator.pop(context, true); // Return true on success
        if (respData['message'] != null && respData['alert'] != null) {
             // If there's an alert, we might want to show it, but for now just pop.
             // The caller can handle success message if needed.
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed (${response.statusCode}): ${response.body}')));
      }
    } catch (e) {
      print("DEBUG: Error in SMS Conf: $e");
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  String _formatTimeForBackend(String timeStr) {
    try {
      // If already in HH:mm:ss, return as is
      if (RegExp(r'^\d{2}:\d{2}:\d{2}$').hasMatch(timeStr)) return timeStr;
      
      // If it has AM/PM, attempt to parse (simple heuristic for AM/PM strings like "8:23 AM")
      if (timeStr.contains(RegExp(r'AM|PM', caseSensitive: false))) {
        final parts = timeStr.split(' ');
        final tParts = parts[0].split(':');
        int hour = int.parse(tParts[0]);
        int min = int.parse(tParts[1]);
        if (parts[1].toUpperCase() == 'PM' && hour < 12) hour += 12;
        if (parts[1].toUpperCase() == 'AM' && hour == 12) hour = 0;
        return "${hour.toString().padLeft(2, '0')}:${min.toString().padLeft(2, '0')}:00";
      }
      return timeStr;
    } catch (e) {
      return timeStr; // Fallback
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('New Transaction Detected'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Amount: ${widget.amount}'),
            Text('Type: ${widget.type.toUpperCase()}'),
            Text('Date: ${widget.date} ${widget.time}'),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              decoration: const InputDecoration(labelText: 'Category'),
              initialValue: _selectedCategory,
              items: (widget.type == 'income' ? _incomeCategories : _expenseCategories)
                  .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                  .toList(),
              onChanged: (val) {
                setState(() {
                  _selectedCategory = val;
                });
              },
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _isLoading ? null : _saveTransaction,
          child: _isLoading ? const CircularProgressIndicator(color: Colors.white, strokeWidth: 2) : const Text('Save'),
        ),
      ],
    );
  }
}
