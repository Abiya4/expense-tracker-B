import 'package:flutter_test/flutter_test.dart';
import 'package:expense_tracker/services/sms_service.dart';

void main() {
  group('SmsService Parsing Logic', () {
    // No setUp needed as parseSms is static

    test('Valid HAM: Masked account (X1234)', () {
      String body =
          'Your account XX1234 has been debited by Rs. 500.00 on 12-Feb-2024.';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNotNull);
      expect(result!['amount'], 500.0);
      expect(result['type'], 'expense');
    });

    test('Valid HAM: "sent to" + 12-digit ref', () {
      String body =
          'Rs. 1000.00 sent to John Doe Ref No 123456789012 on 15-Jan-2024.';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNotNull);
      expect(result!['amount'], 1000.0);
      expect(result['type'], 'expense');
    });

    test('Valid HAM: "Sent to" (case insensitive) + 12-digit ref', () {
      String body =
          'Sent to Jane Doe for dinner. Ref 987654321098. Debited Rs. 250';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNotNull);
      expect(result!['amount'], 250.0);
    });

    test('Spam: URL present', () {
      String body =
          'Your account XX1234 has been debited. Click http://bit.ly/claim to claim reward.';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNull);
    });

    test('Invalid: No masked account and no "sent to" pattern', () {
      String body = 'Hello, how are you?';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNull);
    });

    test('Invalid: "Sent to" without 12 digits', () {
      String body = 'Amount sent to John.';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNull); // Should fail because no 12-digit ref
    });

    test('Invalid: 12 digits without "sent to"', () {
      String body = 'Ref No 123456789012 for your transaction.';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNull); // Should fail because no "sent to"
    });

    test('Valid HAM: Mixed case "SeNt To" + ref', () {
      String body =
          'Amount of Rs 150.00 SeNt To UBER India. Ref No 112233445566.';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNotNull);
      expect(result!['amount'], 150.0);
    });

    test('Valid HAM: "sent via ... to" pattern (Federal Bank)', () {
      String body =
          'Rs 50.00 sent via UPI on 17-02-2026 at 18:48:06 to ADNIXPRO TVPM.Ref:641448031517.Not you? Call 18004251199/SMS BLOCKUPI to 98950 88888 -Federal Bank';
      var result = SmsService.parseSms(body, 'TestSender');
      expect(result, isNotNull,
          reason: "Should pars Federal Bank 'sent via...to' format");
      expect(result!['amount'], 50.0);
      expect(result['time'], isNotNull);
    });
  });
}
