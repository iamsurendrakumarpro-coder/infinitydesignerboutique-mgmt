import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import * as usersService from '../../services/users'
import LoadingSpinner from '../../components/common/LoadingSpinner'
import StatusBadge from '../../components/common/StatusBadge'
import {
  ArrowLeft,
  Pencil,
  User,
  Phone,
  Briefcase,
  Calendar,
  Clock,
  IndianRupee,
  Award,
  Shield,
} from 'lucide-react'
import { format } from 'date-fns'

export default function StaffProfileView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [staff, setStaff] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchStaff() {
      try {
        const data = await usersService.getStaff(id)
        setStaff(data.staff || data)
      } catch {
        // Handle error
      } finally {
        setLoading(false)
      }
    }
    fetchStaff()
  }, [id])

  if (loading) return <LoadingSpinner message="Loading profile..." />
  if (!staff) {
    return (
      <div className="card text-center py-12">
        <User className="h-12 w-12 text-slate-300 mx-auto mb-3" />
        <p className="text-sm text-slate-500">Staff member not found</p>
        <button onClick={() => navigate('/admin/staff')} className="btn-primary mt-4">Back to Directory</button>
      </div>
    )
  }

  const details = [
    { icon: User, label: 'Full Name', value: staff.full_name },
    { icon: Phone, label: 'Phone', value: staff.phone ? `+91 ${staff.phone}` : null },
    { icon: Briefcase, label: 'Designation', value: staff.designation },
    { icon: Calendar, label: 'Joining Date', value: staff.joining_date ? format(new Date(staff.joining_date), 'dd MMM yyyy') : null },
    { icon: Clock, label: 'Login Time', value: staff.login_time },
    { icon: Clock, label: 'Logout Time', value: staff.logout_time },
    { icon: IndianRupee, label: 'Weekly Salary', value: staff.weekly_salary ? `₹${staff.weekly_salary}` : null },
    { icon: Shield, label: 'Role', value: staff.role },
  ]

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-slide-up">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="p-2 rounded-xl hover:bg-slate-100 text-slate-500">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-800">Staff Profile</h1>
        </div>
        <button
          onClick={() => navigate(`/admin/staff/${id}/edit`)}
          className="btn-secondary"
        >
          <Pencil className="h-4 w-4" />
          Edit
        </button>
      </div>

      {/* Header Card */}
      <div className="card text-center !py-8">
        <div className="h-20 w-20 rounded-full gradient-primary flex items-center justify-center mx-auto text-white text-2xl font-bold shadow-lg shadow-primary-600/25">
          {staff.full_name?.charAt(0) || '?'}
        </div>
        <h2 className="text-xl font-bold text-slate-800 mt-3">{staff.full_name}</h2>
        <p className="text-sm text-slate-500">{staff.designation || 'Team Member'}</p>
        <div className="mt-2">
          <StatusBadge status={staff.status || 'active'} />
        </div>
      </div>

      {/* Details */}
      <div className="card !p-0 divide-y divide-slate-100">
        {details.map((item, idx) =>
          item.value ? (
            <div key={idx} className="flex items-center gap-3 px-5 py-3.5">
              <div className="h-9 w-9 rounded-xl bg-primary-50 flex items-center justify-center">
                <item.icon className="h-4 w-4 text-primary-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-400 font-medium">{item.label}</p>
                <p className="text-sm font-semibold text-slate-700 truncate capitalize">{item.value}</p>
              </div>
            </div>
          ) : null
        )}
      </div>

      {/* Skills */}
      {staff.skills && staff.skills.length > 0 && (
        <div className="card space-y-3">
          <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
            <Award className="h-4 w-4 text-accent-600" />
            Skills
          </h3>
          <div className="flex flex-wrap gap-2">
            {staff.skills.map((skill, idx) => (
              <span key={idx} className="px-3 py-1.5 rounded-full bg-primary-50 text-primary-700 text-xs font-semibold border border-primary-100">
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Emergency Contact */}
      {staff.emergency_contact && (
        <div className="card space-y-2">
          <h3 className="text-sm font-bold text-slate-700">Emergency Contact</h3>
          <p className="text-sm text-slate-600">
            {staff.emergency_contact.name} — {staff.emergency_contact.phone}
          </p>
        </div>
      )}

      {/* Attendance Summary */}
      {staff.attendance_summary && (
        <div className="card space-y-3">
          <h3 className="text-sm font-bold text-slate-700">Attendance Summary</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center p-3 rounded-xl bg-emerald-50">
              <p className="text-lg font-bold text-emerald-700">{staff.attendance_summary.present || 0}</p>
              <p className="text-xs text-emerald-600">Present</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-red-50">
              <p className="text-lg font-bold text-red-700">{staff.attendance_summary.absent || 0}</p>
              <p className="text-xs text-red-600">Absent</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-amber-50">
              <p className="text-lg font-bold text-amber-700">{staff.attendance_summary.late || 0}</p>
              <p className="text-xs text-amber-600">Late</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
