package com.example.flutter_login_app

import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import android.content.Context

class MainActivity: FlutterActivity() {
    private val METHOD_CHANNEL = "com.example.flutter_login_app/sms_methods"

    companion object {
        private var instance: MainActivity? = null
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        instance = this

        // Schedule Hourly Reminder Worker
        val reminderWorkRequest = PeriodicWorkRequestBuilder<ReminderWorker>(1, TimeUnit.HOURS).build()
        WorkManager.getInstance(applicationContext).enqueueUniquePeriodicWork(
            "sms_reminder_worker",
            androidx.work.ExistingPeriodicWorkPolicy.KEEP,
            reminderWorkRequest
        )

        // Method Channel for Pending SMS Sync
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, METHOD_CHANNEL).setMethodCallHandler { call, result ->
            if (call.method == "getPendingSms") {
                val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
                val pendingSms = prefs.getString("flutter.pending_sms", "[]")
                
                result.success(pendingSms)
            } else if (call.method == "clearPendingSms") {
                val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
                prefs.edit().putString("flutter.pending_sms", "[]").apply()
                result.success(true)
            } else if (call.method == "getCategorizedSms") {
                val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
                val categorizedSms = prefs.getString("flutter.categorized_sms", "[]")
                
                result.success(categorizedSms)
            } else if (call.method == "clearCategorizedSms") {
                val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
                prefs.edit().putString("flutter.categorized_sms", "[]").apply()
                result.success(true)
            } else if (call.method == "setRecentCategory") {
                val type = call.argument<String>("type") ?: "expense"
                val category = call.argument<String>("category") ?: "Uncategorized"
                
                val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
                val key = if (type == "income") "flutter.recent_income_category" else "flutter.recent_expense_category"
                
                prefs.edit().putString(key, category).apply()
                result.success(true)
            } else {
                result.notImplemented()
            }
        }
    }
}
