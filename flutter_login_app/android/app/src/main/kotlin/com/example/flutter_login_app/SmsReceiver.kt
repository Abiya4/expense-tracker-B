package com.example.flutter_login_app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.os.Build
import androidx.core.app.NotificationCompat
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.util.Date

class SmsReceiver : BroadcastReceiver() {
    private val PREFS_NAME = "FlutterSharedPreferences" // Default Flutter Prefs
    private val PREFS_KEY = "flutter.pending_sms" // Key accessible from Flutter (with prefix)

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Telephony.Sms.Intents.SMS_RECEIVED_ACTION) {
            val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
            for (message in messages) {
                val sender = message.originatingAddress
                val body = message.messageBody
                val timestamp = message.timestampMillis

                if (isExpenseSms(sender, body)) {
                    // 1. Save to SharedPreferences for persistence
                    saveSmsLocally(context, sender, body, timestamp)

                    // 2. Show Notification
                    showNotification(context, body)

                    // 3. Try sending to Flutter (if running)
                    MainActivity.sendSms(sender, body)
                }
            }
        }
    }

    private fun isExpenseSms(sender: String?, body: String?): Boolean {
        if (body == null || body.isBlank() || sender == null || sender.isBlank()) {
            android.util.Log.d("SMS_FILTER", "REJECTED: Body or Sender is null/blank")
            return false
        }
        
        android.util.Log.d("SMS_FILTER", "========== ANALYZING SMS ==========")
        val lowerBody = body.lowercase()
        android.util.Log.d("SMS_FILTER", "Sender: $sender")
        android.util.Log.d("SMS_FILTER", "Body: $body")
        
        // Validate Sender Address Pattern
        val senderPattern = Regex("^[A-Z]{2}-[A-Z0-9]{5,12}(-[A-Z])?$")
        if (!senderPattern.matches(sender.uppercase())) {
            android.util.Log.d("SMS_FILTER", "REJECTED: Sender does not match bank pattern")
            return false
        }
        
        // ========== ONLY CHECK: MASKED ACCOUNT AND NO LINKS ==========
        // HAM = Has masked account like X1234, XX1234, XXX5678 (uppercase X + digits)
        // OR "sent to" + 12-digit reference number
        // AND does NOT contain any URLs
        val maskedAccountPattern = Regex("X+\\d{3,4}")
        val hasMaskedAccount = maskedAccountPattern.containsMatchIn(body)
        
        // New logic: "sent to" ... 12 digit ref number
        // Relaxed regex: just "sent" followed by "to" with anything in between
        val sentToPattern = Regex("sent.+?to", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
        val hasSentTo = sentToPattern.containsMatchIn(body)
        
        // Relaxed Ref number: just look for 12 continuous digits, boundary checks might be failing on some chars
        val refNoPattern = Regex("\\d{12}")
        val hasRefNo = refNoPattern.containsMatchIn(body)

        android.util.Log.d("SMS_FILTER", "Has masked account: $hasMaskedAccount")
        android.util.Log.d("SMS_FILTER", "Has SentTo pattern: $hasSentTo")
        android.util.Log.d("SMS_FILTER", "Has RefNo: $hasRefNo")
        
        val isValidHam = (hasMaskedAccount || (hasSentTo && hasRefNo))

        if (!isValidHam) {
            android.util.Log.d("SMS_FILTER", "REJECTED: No masked account or valid 'sent to' pattern")
            return false
        }

        // Check for URLs
        val urlPatterns = listOf("http://", "https://", "www.", "bit.ly", "tinyurl", ".com", ".in")
        val hasUrl = urlPatterns.any { lowerBody.contains(it) }
        android.util.Log.d("SMS_FILTER", "Contains URL: $hasUrl")

        if (hasUrl) {
            android.util.Log.d("SMS_FILTER", "REJECTED: Contains URL (Phishing)")
            return false
        }

        android.util.Log.d("SMS_FILTER", "✅ ACCEPTED AS HAM - Valid account and no links!")
        return true
    }

    private fun saveSmsLocally(context: Context, sender: String?, body: String?, timestamp: Long) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val existingJson = prefs.getString(PREFS_KEY, "[]")
        try {
            val jsonArray = JSONArray(existingJson)
            val smsObj = JSONObject()
            smsObj.put("sender", sender)
            smsObj.put("body", body)
            smsObj.put("timestamp", timestamp)
            jsonArray.put(smsObj)
            
            // Flutter SharedPreferences plugin expects values to be prefixed with "flutter." if accessed via the plugin
            // BUT wait, if we write to "FlutterSharedPreferences", the plugin reads from there.
            // The key in Dart will be "pending_sms" if we use SharedPreferences.getInstance() 
            // AND we prefix the key with "flutter." in the XML file. 
            // So here we should write to key "flutter.pending_sms". 
            // YES, the PREFS_KEY is defined as "flutter.pending_sms".
            
            prefs.edit().putString(PREFS_KEY, jsonArray.toString()).apply()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun showNotification(context: Context, body: String?) {
        val channelId = "expense_tracker_sms"
        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "Expense Alerts", NotificationManager.IMPORTANCE_HIGH)
            notificationManager.createNotificationChannel(channel)
        }

        // Intent to open app
        val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
        val pendingIntent = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.sym_action_chat) // Default icon, replace if available
            .setContentTitle("New Expense Detected")
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }
}
