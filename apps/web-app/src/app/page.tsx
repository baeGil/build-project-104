"use client";

import Link from "next/link";
import { HealthStatus } from "@/components/HealthStatus";
import {
  FileText,
  MessageSquare,
  Clock,
  Database,
  Activity,
  ArrowRight,
} from "lucide-react";

// Mock stats - in real app these would come from API
const stats = [
  { label: "Tài liệu đã nhập", value: "12,458", icon: Database, trend: "+234 tuần này" },
  { label: "Rà soát gần đây", value: "156", icon: FileText, trend: "+12 hôm nay" },
  { label: "Độ trễ trung bình", value: "1.2s", icon: Clock, trend: "-0.3s so với tuần trước" },
  { label: "Tình trạng hệ thống", value: "98.5%", icon: Activity, trend: "Hoạt động bình thường" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Trang chủ</h1>
          <p className="text-muted mt-1">
            Hệ thống AI Rà soát Hợp đồng Pháp lý Việt Nam
          </p>
        </div>
        <div className="flex items-center gap-4 bg-white px-4 py-2 rounded-lg border border-slate-200">
          <span className="text-sm text-muted">Tình trạng API:</span>
          <HealthStatus />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted">{stat.label}</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    {stat.value}
                  </p>
                </div>
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Icon className="w-5 h-5 text-primary" />
                </div>
              </div>
              <p className="text-xs text-green-600 mt-3 font-medium">
                {stat.trend}
              </p>
            </div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          href="/review"
          className="group bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-primary/30 transition-all"
        >
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-colors">
              <FileText className="w-6 h-6 text-primary group-hover:text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-slate-900 group-hover:text-primary transition-colors">
                Rà soát hợp đồng
              </h3>
              <p className="text-muted mt-1">
                Tải lên hoặc dán nội dung hợp đồng để phân tích tuân thủ
                pháp luật Việt Nam.
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted group-hover:text-primary group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

        <Link
          href="/chat"
          className="group bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-primary/30 transition-all"
        >
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-colors">
              <MessageSquare className="w-6 h-6 text-primary group-hover:text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-slate-900 group-hover:text-primary transition-colors">
                Tư vấn pháp lý
              </h3>
              <p className="text-muted mt-1">
                Trò chuyện với AI về các vấn đề pháp lý Việt Nam và nhận câu trả lời
                có trích dẫn từ hệ thống pháp luật.
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted group-hover:text-primary group-hover:translate-x-1 transition-all" />
          </div>
        </Link>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="p-6 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">
            Hoạt động gần đây
          </h2>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {[
              {
                action: "Hợp đồng đã rà soát",
                detail: "Thỏa thuận Dịch vụ Phần mềm - 12 điều khoản đã phân tích",
                time: "2 phút trước",
                status: "Hoàn thành",
              },
              {
                action: "Câu hỏi pháp lý đã trả lời",
                detail: "Câu hỏi về chấm dứt hợp đồng lao động",
                time: "15 phút trước",
                status: "Hoàn thành",
              },
              {
                action: "Tài liệu đã nhập liệu",
                detail: "50 tài liệu pháp lý mới đã thêm vào hệ thống",
                time: "1 giờ trước",
                status: "Hoàn thành",
              },
            ].map((activity, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0"
              >
                <div>
                  <p className="font-medium text-slate-900">{activity.action}</p>
                  <p className="text-sm text-muted">{activity.detail}</p>
                </div>
                <div className="text-right">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    {activity.status}
                  </span>
                  <p className="text-xs text-muted mt-1">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
