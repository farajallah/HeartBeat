// Chart.js utilities for Time Attendance Tracker

class AttendanceCharts {
    constructor() {
        this.charts = {};
    }

    // Create monthly bar chart
    createMonthlyChart(canvasId, labels, workedData, requiredData) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        // Destroy existing chart if it exists
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Worked Hours',
                        data: workedData,
                        backgroundColor: 'rgba(59, 130, 246, 0.5)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Required Hours',
                        data: requiredData,
                        backgroundColor: 'rgba(239, 68, 68, 0.5)',
                        borderColor: 'rgba(239, 68, 68, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Hours'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Month'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toFixed(1) + 'h';
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });

        this.charts[canvasId] = chart;
        return chart;
    }

    // Create balance line chart
    createBalanceChart(canvasId, labels, balanceData) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        // Destroy existing chart if it exists
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Balance (Hours)',
                        data: balanceData,
                        borderColor: 'rgba(16, 185, 129, 1)',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Balance (Hours)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Month'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    const value = context.parsed.y;
                                    label += (value >= 0 ? '+' : '') + value.toFixed(1) + 'h';
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });

        this.charts[canvasId] = chart;
        return chart;
    }

    // Create daily attendance heatmap
    createAttendanceHeatmap(canvasId, dailyData) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        // Destroy existing chart if it exists
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        // Process data for heatmap
        const processedData = dailyData.map(day => ({
            x: day.date.getDate(),
            y: day.date.getMonth() + 1,
            v: day.effective_minutes / 60 // Convert to hours
        }));

        const chart = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Daily Hours',
                    data: processedData,
                    backgroundColor: function(context) {
                        const value = context.parsed.v;
                        if (value === 0) return 'rgba(229, 231, 235, 1)';
                        if (value < 4) return 'rgba(254, 202, 202, 1)';
                        if (value < 6) return 'rgba(252, 211, 77, 1)';
                        if (value < 8) return 'rgba(134, 239, 172, 1)';
                        return 'rgba(16, 185, 129, 1)';
                    },
                    pointRadius: 8,
                    pointHoverRadius: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        min: 1,
                        max: 31,
                        title: {
                            display: true,
                            text: 'Day of Month'
                        }
                    },
                    y: {
                        type: 'linear',
                        min: 1,
                        max: 12,
                        title: {
                            display: true,
                            text: 'Month'
                        },
                        ticks: {
                            callback: function(value) {
                                const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                                return months[value - 1] || '';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const date = new Date(context.parsed.y, context.parsed.x - 1);
                                const dateStr = date.toLocaleDateString();
                                const hours = context.parsed.v;
                                return `${dateStr}: ${hours.toFixed(1)}h`;
                            }
                        }
                    }
                }
            }
        });

        this.charts[canvasId] = chart;
        return chart;
    }

    // Destroy all charts
    destroyAll() {
        Object.keys(this.charts).forEach(key => {
            if (this.charts[key]) {
                this.charts[key].destroy();
            }
        });
        this.charts = {};
    }

    // Utility function to format minutes to hours display
    static formatMinutesToHours(minutes) {
        if (minutes >= 0) {
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return `+${hours}h ${mins}m`;
        } else {
            const absMinutes = Math.abs(minutes);
            const hours = Math.floor(absMinutes / 60);
            const mins = absMinutes % 60;
            return `-${hours}h ${mins}m`;
        }
    }

    // Utility function to get color based on balance
    static getBalanceColor(balance) {
        if (balance > 0) return '#10b981'; // green
        if (balance < 0) return '#ef4444'; // red
        return '#6b7280'; // gray
    }
}

// Initialize charts when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.attendanceCharts = new AttendanceCharts();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AttendanceCharts;
}
