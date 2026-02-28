package com.example.flutter_login_app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject

class ReminderWorker(appContext: Context, workerParams: WorkerParameters) : Worker(appContext, workerParams) {

    override fun doWork(): Result {
        val prefs = applicationContext.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val pendingJson = prefs.getString("flutter.pending_sms", "[]")

        if (pendingJson == null || pendingJson == "[]") {
            return Result.success() // Nothing pending
        }

        try {
            val pendingArray = JSONArray(pendingJson)
            for (i in 0 until pendingArray.length()) {
                val smsObj = pendingArray.getJSONObject(i)
                val sender = smsObj.optString("sender")
                val body = smsObj.optString("body")
                val timestamp = smsObj.optLong("timestamp")

                // Reshow notification for this pending expense
                reshowNotification(applicationContext, sender, body, timestamp)
            }
        } catch (e: Exception) {
            e.printStackTrace()
            return Result.failure()
        }

        return Result.success()
    }

    private fun reshowNotification(context: Context, sender: String?, body: String?, timestamp: Long) {
        val channelId = "expense_tracker_sms"
        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "Expense Alerts", NotificationManager.IMPORTANCE_HIGH)
            notificationManager.createNotificationChannel(channel)
        }

        val notificationId = (timestamp % Int.MAX_VALUE).toInt()

        val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
        val pendingIntent = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        // Determine if Income or Expense
        val isIncome = body?.lowercase()?.let { it.contains("credited") || it.contains("received") } ?: false
        val prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val recentCategory = if (isIncome) {
            prefs.getString("flutter.recent_income_category", "Salary") ?: "Salary"
        } else {
            prefs.getString("flutter.recent_expense_category", "Food") ?: "Food"
        }

        // 1. Cancel Action
        val cancelIntent = Intent(context, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_CANCEL_EXPENSE
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notificationId)
            putExtra(NotificationActionReceiver.EXTRA_TIMESTAMP, timestamp)
        }
        val cancelPendingIntent = PendingIntent.getBroadcast(
            context,
            notificationId * 10,
            cancelIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val cancelAction = NotificationCompat.Action.Builder(
            android.R.drawable.ic_delete,
            "Cancel",
            cancelPendingIntent
        ).build()

        // 2. Recent Category Action (Instant Save)
        val recentIntent = Intent(context, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_CATEGORY_RECENT
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notificationId)
            putExtra(NotificationActionReceiver.EXTRA_SENDER, sender)
            putExtra(NotificationActionReceiver.EXTRA_BODY, body)
            putExtra(NotificationActionReceiver.EXTRA_TIMESTAMP, timestamp)
            putExtra(NotificationActionReceiver.EXTRA_RECENT_CATEGORY, recentCategory)
        }
        val recentPendingIntent = PendingIntent.getBroadcast(
            context,
            notificationId * 10 + 1,
            recentIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val recentAction = NotificationCompat.Action.Builder(
            android.R.drawable.ic_menu_save,
            recentCategory,
            recentPendingIntent
        ).build()

        // 3. Other Action (Direct Reply)
        val categorizeIntent = Intent(context, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_CATEGORY_SUBMIT
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notificationId)
            putExtra(NotificationActionReceiver.EXTRA_SENDER, sender)
            putExtra(NotificationActionReceiver.EXTRA_BODY, body)
            putExtra(NotificationActionReceiver.EXTRA_TIMESTAMP, timestamp)
        }
        val categorizePendingIntent = PendingIntent.getBroadcast(
            context,
            notificationId * 10 + 2,
            categorizeIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
        )
        val remoteInput = androidx.core.app.RemoteInput.Builder(SmsReceiver.REPLY_INPUT_KEY)
            .setLabel("Type category")
            .build()
        val categorizeAction = NotificationCompat.Action.Builder(
            android.R.drawable.ic_input_add,
            "Other",
            categorizePendingIntent
        ).addRemoteInput(remoteInput).build()

        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.sym_action_chat)
            .setContentTitle("Reminder: Pending Expense")
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)
            .addAction(recentAction)
            .addAction(categorizeAction)
            .addAction(cancelAction)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(notificationId, notification)
    }
}
