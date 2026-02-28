package com.example.flutter_login_app

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.RemoteInput
import android.content.SharedPreferences
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject

class NotificationActionReceiver : BroadcastReceiver() {
    
    companion object {
        const val ACTION_CATEGORY_SUBMIT = "com.example.flutter_login_app.ACTION_CATEGORY_SUBMIT"
        const val ACTION_CATEGORY_RECENT = "com.example.flutter_login_app.ACTION_CATEGORY_RECENT"
        const val ACTION_CANCEL_EXPENSE = "com.example.flutter_login_app.ACTION_CANCEL_EXPENSE"
        const val EXTRA_NOTIFICATION_ID = "notification_id"
        const val EXTRA_SENDER = "sender"
        const val EXTRA_BODY = "body"
        const val EXTRA_TIMESTAMP = "timestamp"
        const val EXTRA_RECENT_CATEGORY = "recent_category"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val notificationId = intent.getIntExtra(EXTRA_NOTIFICATION_ID, 0)
        val sender = intent.getStringExtra(EXTRA_SENDER)
        val body = intent.getStringExtra(EXTRA_BODY)
        val timestamp = intent.getLongExtra(EXTRA_TIMESTAMP, 0)

        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        when (intent.action) {
            ACTION_CANCEL_EXPENSE -> {
                // Remove from pending
                removeSmsFromPending(context, timestamp)
                // Dismiss notification
                notificationManager.cancel(notificationId)
                Toast.makeText(context, "Expense ignored", Toast.LENGTH_SHORT).show()
            }
            ACTION_CATEGORY_RECENT -> {
                val category = intent.getStringExtra(EXTRA_RECENT_CATEGORY) ?: "Uncategorized"
                
                // 1. Save categorized SMS so Flutter can push it later
                saveCategorizedSms(context, sender, body, timestamp, category)
                // 2. Remove from pending list
                removeSmsFromPending(context, timestamp)
                
                notificationManager.cancel(notificationId)
                Toast.makeText(context, "Saved as $category", Toast.LENGTH_SHORT).show()
            }
            ACTION_CATEGORY_SUBMIT -> {
                val remoteInput = RemoteInput.getResultsFromIntent(intent)
                if (remoteInput != null) {
                    val category = remoteInput.getCharSequence(SmsReceiver.REPLY_INPUT_KEY)?.toString()?.trim()
                    
                    if (!category.isNullOrEmpty()) {
                        // 1. Save categorized SMS so Flutter can push it later
                        saveCategorizedSms(context, sender, body, timestamp, category)
                        // 2. Remove from pending list
                        removeSmsFromPending(context, timestamp)
                        
                        notificationManager.cancel(notificationId)
                        Toast.makeText(context, "Saved as $category", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }

    private fun removeSmsFromPending(context: Context, timestamp: Long) {
        val prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val existingJson = prefs.getString("flutter.pending_sms", "[]")
        try {
            val jsonArray = JSONArray(existingJson)
            val updatedArray = JSONArray()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                if (obj.getLong("timestamp") != timestamp) {
                    updatedArray.put(obj)
                }
            }
            prefs.edit().putString("flutter.pending_sms", updatedArray.toString()).apply()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun saveCategorizedSms(context: Context, sender: String?, body: String?, timestamp: Long, category: String) {
        val prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val existingJson = prefs.getString("flutter.categorized_sms", "[]")
        try {
            val jsonArray = JSONArray(existingJson)
            val smsObj = JSONObject()
            smsObj.put("sender", sender)
            smsObj.put("body", body)
            smsObj.put("timestamp", timestamp)
            smsObj.put("category", category)
            jsonArray.put(smsObj)
            prefs.edit().putString("flutter.categorized_sms", jsonArray.toString()).apply()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
