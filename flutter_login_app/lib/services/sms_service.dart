import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';
import '../screens/sms_confirmation_dialog.dart';

class SmsService {
  static const EventChannel _eventChannel = EventChannel('com.example.flutter_login_app/sms');
  static const MethodChannel _methodChannel = MethodChannel('com.example.flutter_login_app/sms_methods');
  
  final BuildContext context;
  final int userId;
  final VoidCallback? onRefresh;

  SmsService(this.context, this.userId, {this.onRefresh});

  void initListener() async {
    // Request permissions
    var status = await Permission.sms.status;
    if (!status.isGranted) {
      if (await Permission.notification.status.isDenied) {
        await Permission.notification.request();
      }
      status = await Permission.sms.request();
      if (!status.isGranted) {
        print("SMS permissions not granted");
        return;
      }
    }

    // 1 & 1.5. Sync offline SMS (pending & categorized)
    syncOfflineSms();

    print("SMS Listener Initialized (On Resume/Start Only)");
  }

  Future<void> syncOfflineSms() async {
    await _syncPendingSms();
    await _syncCategorizedSms();
  }

  Future<void> _syncPendingSms() async {
    try {
      final String? jsonString = await _methodChannel.invokeMethod('getPendingSms');
      if (jsonString == null || jsonString == "[]") return;

      print("DEBUG: Pending SMS JSON: $jsonString");
      List<dynamic> smsList = jsonDecode(jsonString);
      List<Map<String, dynamic>> expensesToSync = [];

      for (var sms in smsList) {
        String body = sms['body'] ?? "";
        String sender = sms['sender'] ?? "";
        // Parse using the same logic
        var parsed = parseSms(body, sender);
        if (parsed != null) {
          expensesToSync.add(parsed);
        }
      }

      if (expensesToSync.isNotEmpty) {
        await _sendPendingToBackend(expensesToSync);
      }
      
      // Clear pending list after successfully parsing & transmitting
      if (smsList.isNotEmpty) {
        await _methodChannel.invokeMethod('clearPendingSms');
        if (onRefresh != null) onRefresh!();
      }
    } catch (e) {
      print("Error syncing pending SMS: $e");
    }
  }

  Future<void> _sendPendingToBackend(List<Map<String, dynamic>> expenses) async {
    try {
      final response = await http.post(
        Uri.parse("${Constants.baseUrl}/expenses/server_sync"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"expenses": expenses}),
      );
      print("Sync Response: ${response.statusCode} ${response.body}");
    } catch (e) {
      print("Backend Sync Error: $e");
    }
  }

  Future<void> _syncCategorizedSms() async {
    try {
      final String? jsonString = await _methodChannel.invokeMethod('getCategorizedSms');
      if (jsonString == null || jsonString == "[]") return;

      print("DEBUG: Categorized SMS JSON: $jsonString");
      List<dynamic> smsList = jsonDecode(jsonString);
      
      for (var sms in smsList) {
        String body = sms['body'] ?? "";
        String sender = sms['sender'] ?? "";
        String userCategory = sms['category'] ?? "Uncategorized";
        
        // Parse to get amount and date using normal logic
        var parsed = parseSms(body, sender, injectCategory: userCategory);
        if (parsed != null) {
          // Push directly as confirmed expense
          await _sendConfirmedToBackend(parsed, userCategory);
        }
      }
      
      // CRITICAL: We MUST clear the categorized list after pushing them to backend
      if (smsList.isNotEmpty) {
        await _methodChannel.invokeMethod('clearCategorizedSms');
        if (onRefresh != null) onRefresh!();
      }
    } catch (e) {
      print("Error syncing categorized SMS: $e");
    }
  }

  Future<void> _sendConfirmedToBackend(Map<String, dynamic> parsedSms, String category) async {
    try {
      final response = await http.post(
        Uri.parse("${Constants.baseUrl}/expenses"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "amount": parsedSms['amount'],
          "date": parsedSms['date'],
          "time": parsedSms['time'],
          "category": category,
          "type": parsedSms['type'],
          "status": "confirmed", // Since user categorized it via notification
          "entry_method": "sms"
        }),
      );
      print("Sync Categorized Response: ${response.statusCode} ${response.body}");
    } catch (e) {
      print("Backend Categorized Sync Error: $e");
    }
  }

  // Helper Key Logic for Parsing
  // Made public and static for testing
  static Map<String, dynamic>? parseSms(String body, String sender, {String? injectCategory}) {
    // ========== SENDER CHECK ==========
    RegExp senderPattern = RegExp(r'^[A-Z]{2}-[A-Z0-9]{5,12}(-[A-Z])?$');
    if (!senderPattern.hasMatch(sender.toUpperCase())) {
      print('❌ SMS REJECTED: Sender ($sender) does not match bank pattern');
      return null;
    }

    // ========== ONLY CHECK: MASKED ACCOUNT AND NO LINKS ==========
    // HAM = Has masked account like X1234, XX1234, XXX5678 (uppercase X + digits)
    // OR "sent to" + 12-digit reference number
    // AND does NOT contain any URLs (phishing protection)
    RegExp maskedAccountPattern = RegExp(r'X+\d{3,4}');
    bool hasMaskedAccount = maskedAccountPattern.hasMatch(body);

    // New logic: "sent to" ... 12 digit ref number
    // New logic: "sent to" ... 12 digit ref number
    // Allow for words between sent and to (e.g. "sent via UPI to")
    RegExp sentToPattern = RegExp(r'sent\b.+?\bto\b', caseSensitive: false);
    bool hasSentTo = sentToPattern.hasMatch(body);
    RegExp refNoPattern = RegExp(r'\b\d{12}\b'); // Exactly 12 digits
    bool hasRefNo = refNoPattern.hasMatch(body);
    
    // URL Check
    List<String> urlPatterns = ['http://', 'https://', 'www.', 'bit.ly', 'tinyurl', '.com', '.in'];
    bool hasUrl = urlPatterns.any((pattern) => body.toLowerCase().contains(pattern));

    // Valid HAM logic
    bool isValidHam = (hasMaskedAccount || (hasSentTo && hasRefNo)) && !hasUrl;

    if (!isValidHam) {
      if (hasUrl) print('❌ SMS REJECTED: Contains phishing link');
      else if (!hasMaskedAccount && !(hasSentTo && hasRefNo)) print('❌ SMS REJECTED: No masked account or reference number pattern');
      return null;
    }

    // ========== PARSE TRANSACTION DETAILS ==========
    String lowerBody = body.toLowerCase();
    
    // Amount regex: Try with Rs/INR first, then fallback to plain numbers
    RegExp amountWithPrefix = RegExp(r'(?:Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)', caseSensitive: false);
    RegExp amountWithoutPrefix = RegExp(r'(?:debited|credited|paid|received)\s+(?:by\s+)?(\d+(?:\.\d{2})?)', caseSensitive: false);

    // 3. Type Detection
    String type = '';
    RegExp expenseRegex = RegExp(r'\b(debited|debit|spent|dr|paid|sent|withdrawn|transferred)\b', caseSensitive: false);
    RegExp incomeRegex = RegExp(r'\b(credited|credit|received|cr|added|deposited)\b', caseSensitive: false);

    if (expenseRegex.hasMatch(lowerBody)) type = 'expense';
    else if (incomeRegex.hasMatch(lowerBody)) type = 'income';
    else {
      print('❌ SMS PARSE FAILED: No transaction keyword found');
      return null;
    }

    // 4. Extract Amount
    Match? amountMatch = amountWithPrefix.firstMatch(body);
    if (amountMatch == null) {
      // Try without prefix
      amountMatch = amountWithoutPrefix.firstMatch(body);
    }
    
    double amount = 0.0;
    if (amountMatch != null) {
      String rawAmount = amountMatch.group(1)!.replaceAll(',', '');
      amount = double.tryParse(rawAmount) ?? 0.0;
      print('✅ Amount extracted: Rs.$amount');
    } else {
      print('❌ SMS PARSE FAILED: No amount found in: $body');
      return null;
    }

    // 5. Extract and Format Date
    RegExp dateRegex = RegExp(r'(\d{1,2})[-/\s]?([A-Za-z]{3})[-/\s]?(\d{2,4})', caseSensitive: false);
    Match? dateMatch = dateRegex.firstMatch(body);
    String finalDateStr = DateTime.now().toString().split(' ')[0]; // Fallback YYYY-MM-DD

    if (dateMatch != null) {
      try {
        String day = dateMatch.group(1)!.padLeft(2, '0');
        String monthStr = dateMatch.group(2)!.toUpperCase();
        String year = dateMatch.group(3)!;
        if (year.length == 2) year = "20$year";

        const months = {
          'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
          'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
        };
        String? month = months[monthStr];
        if (month != null) {
          finalDateStr = "$year-$month-$day";
        }
      } catch (e) {
        print("Date parse error: $e");
      }
    }

    // 6. Extract Time in 24h format HH:mm:ss
    final now = DateTime.now();
    String time = "${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')}";

    return {
      "amount": amount,
      "date": finalDateStr,
      "time": time, 
      "category": injectCategory ?? "Uncategorized", // Use injected category if available
      "type": type,
    };
  }

  // _processForegroundMessage removed since we rely purely on Android notifications now.
}
