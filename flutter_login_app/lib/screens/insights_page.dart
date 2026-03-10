import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:fl_chart/fl_chart.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:intl/intl.dart';
import '../utils/constants.dart';

class InsightsPage extends StatefulWidget {
  final int userId;
  const InsightsPage({super.key, required this.userId});

  @override
  State<InsightsPage> createState() => _InsightsPageState();
}

class _InsightsPageState extends State<InsightsPage> {
  final String baseUrl = Constants.baseUrl;
  bool isLoading = true;
  List<dynamic> allExpenses = [];

  // Calendar
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;
  List<dynamic> _selectedDayTransactions = [];

  // Insights
  Map<String, double> categorySpending = {};
  Map<DateTime, double> dailySpending = {};
  DateTime? highestSpendingDay;
  double highestSpendingAmount = 0.0;
  String highestSpendingDayStr = "No Data";

  @override
  void initState() {
    super.initState();
    _focusedDay = DateTime.now();
    _selectedDay = _focusedDay;
    fetchExpenses();
  }

  Future<void> fetchExpenses() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(Uri.parse("$baseUrl/expenses"));
      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        allExpenses = data;
        processInsights();
        _updateSelectedDayTransactions(_selectedDay!);
      }
    } catch (e) {
      print("Error fetching expenses: $e");
    } finally {
      setState(() => isLoading = false);
    }
  }

  void processInsights() {
    categorySpending.clear();
    dailySpending.clear();
    highestSpendingAmount = 0.0;
    highestSpendingDay = null;
    highestSpendingDayStr = "No Data";

    // Filter for the currently focused month
    DateTime startOfMonth = DateTime(_focusedDay.year, _focusedDay.month, 1);
    DateTime endOfMonth = DateTime(_focusedDay.year, _focusedDay.month + 1, 0);

    for (var item in allExpenses) {
      if (item['type'] == 'expense') {
        double amount = (item['amount'] as num).toDouble();
        String category = item['category'] ?? 'Uncategorized';
        String dateStr = item['date'];
        DateTime date = DateTime.parse(dateStr);
        DateTime normalizedDate = DateTime(date.year, date.month, date.day);

        // Populate dailySpending globally for markers
        dailySpending[normalizedDate] =
            (dailySpending[normalizedDate] ?? 0) + amount;

        // For Pie Chart & Highest Day -> Only consider THIS MONTH
        if (date.isAfter(startOfMonth.subtract(const Duration(days: 1))) &&
            date.isBefore(endOfMonth.add(const Duration(days: 1)))) {
          categorySpending[category] =
              (categorySpending[category] ?? 0) + amount;

          if ((dailySpending[normalizedDate] ?? 0) > highestSpendingAmount) {
            highestSpendingAmount = dailySpending[normalizedDate]!;
            highestSpendingDay = normalizedDate;
          }
        }
      }
    }

    if (highestSpendingDay != null) {
      highestSpendingDayStr = DateFormat('MMM d').format(highestSpendingDay!);
    } else {
      highestSpendingDayStr = "No expenses";
    }
  }

  void _updateSelectedDayTransactions(DateTime date) {
    _selectedDayTransactions = allExpenses.where((item) {
      DateTime itemDate = DateTime.parse(item['date']);
      return itemDate.year == date.year &&
          itemDate.month == date.month &&
          itemDate.day == date.day;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050B18),
      appBar: AppBar(
        backgroundColor: const Color(0xFF050B18),
        elevation: 0,
        title: const Text("Insights & Analytics",
            style: TextStyle(color: Colors.white)),
        centerTitle: true,
        leading: const BackButton(color: Colors.white),
      ),
      body: isLoading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF2FE6D1)))
          : RefreshIndicator(
              onRefresh: fetchExpenses,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildHighestSpendingCard(),
                    const SizedBox(height: 24),
                    _buildPieChartSection(),
                    const SizedBox(height: 24),
                    _buildCalendarSection(),
                    const SizedBox(height: 16),
                    _buildDayTransactionsList(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildHighestSpendingCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1E2746), Color(0xFF161D32)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.red.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.flash_on, color: Colors.red, size: 28),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("Highest Spending Day",
                  style: TextStyle(color: Colors.white54, fontSize: 12)),
              const SizedBox(height: 4),
              Text("₹${highestSpendingAmount.toStringAsFixed(2)}",
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold)),
              Text(highestSpendingDayStr,
                  style: const TextStyle(color: Colors.white38, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPieChartSection() {
    if (categorySpending.isEmpty) {
      return const Center(
          child: Text("No expense data for this month",
              style: TextStyle(color: Colors.white38)));
    }

    // Prepare sections
    List<PieChartSectionData> sections = [];
    int index = 0;
    List<Color> colors = [
      const Color(0xFF2FE6D1),
      const Color(0xFF8F5AFF),
      const Color(0xFFFFB347),
      const Color(0xFFFF6B6B),
      const Color(0xFF4ECDC4),
    ];

    categorySpending.forEach((category, amount) {
      final color = colors[index % colors.length];

      sections.add(PieChartSectionData(
        color: color,
        value: amount,
        title: amount.toStringAsFixed(0), // Shorten for view
        radius: 50.0,
        titleStyle: const TextStyle(
            fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
      ));
      index++;
    });

    return Column(
      children: [
        const Text("Spending by Category",
            style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 20),
        SizedBox(
          height: 200,
          child: PieChart(
            PieChartData(
              sections: sections,
              centerSpaceRadius: 40,
              sectionsSpace: 2,
            ),
          ),
        ),
        const SizedBox(height: 20),
        // Legend
        Wrap(
          spacing: 16,
          runSpacing: 8,
          children: categorySpending.keys.map((cat) {
            int i = categorySpending.keys.toList().indexOf(cat);
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                      color: colors[i % colors.length], shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Text(cat,
                    style:
                        const TextStyle(color: Colors.white70, fontSize: 12)),
              ],
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildCalendarSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text("Daily History",
            style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.05),
            borderRadius: BorderRadius.circular(16),
          ),
          child: TableCalendar(
            firstDay: DateTime.utc(2020, 1, 1),
            lastDay: DateTime.utc(2030, 12, 31),
            focusedDay: _focusedDay,
            calendarFormat: CalendarFormat.month,
            selectedDayPredicate: (day) => isSameDay(_selectedDay, day),
            onDaySelected: (selectedDay, focusedDay) {
              setState(() {
                _selectedDay = selectedDay;
                _focusedDay = focusedDay;
                _updateSelectedDayTransactions(selectedDay);
              });
            },
            onPageChanged: (focusedDay) {
              setState(() {
                _focusedDay = focusedDay;
                processInsights();
              });
            },
            calendarStyle: CalendarStyle(
              defaultTextStyle: const TextStyle(color: Colors.white),
              weekendTextStyle: const TextStyle(color: Colors.white70),
              selectedDecoration: const BoxDecoration(
                color: Color(0xFF2FE6D1),
                shape: BoxShape.circle,
              ),
              todayDecoration: BoxDecoration(
                color: const Color(0xFF2FE6D1).withOpacity(0.3),
                shape: BoxShape.circle,
              ),
              markerDecoration: const BoxDecoration(
                color: Colors.redAccent,
                shape: BoxShape.circle,
              ),
            ),
            headerStyle: const HeaderStyle(
              formatButtonVisible: false,
              titleCentered: true,
              titleTextStyle: TextStyle(color: Colors.white, fontSize: 16),
              leftChevronIcon: Icon(Icons.chevron_left, color: Colors.white),
              rightChevronIcon: Icon(Icons.chevron_right, color: Colors.white),
            ),
            eventLoader: (day) {
              DateTime normalized = DateTime(day.year, day.month, day.day);
              return dailySpending.containsKey(normalized) ? [1] : [];
            },
          ),
        ),
      ],
    );
  }

  Widget _buildDayTransactionsList() {
    if (_selectedDayTransactions.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20),
          child: Text(
            "No transactions on ${DateFormat('MMM d').format(_selectedDay!)}",
            style: const TextStyle(color: Colors.white38),
          ),
        ),
      );
    }

    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _selectedDayTransactions.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final item = _selectedDayTransactions[index];
        bool isIncome = item['type'] == 'income';
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.05),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isIncome
                      ? Colors.green.withOpacity(0.1)
                      : Colors.red.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isIncome ? Icons.arrow_downward : Icons.arrow_upward,
                  color: isIncome ? Colors.green : Colors.red,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item['category'],
                        style: const TextStyle(
                            color: Colors.white, fontWeight: FontWeight.bold)),
                    Text(item['time'],
                        style: const TextStyle(
                            color: Colors.white54, fontSize: 12)),
                  ],
                ),
              ),
              Text(
                "${isIncome ? '+' : '-'}₹${(item['amount'] as num).toStringAsFixed(2)}",
                style: TextStyle(
                  color: isIncome ? Colors.green : Colors.redAccent,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
