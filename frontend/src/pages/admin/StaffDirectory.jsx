import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import * as usersService from '../../services/users'
import StatusBadge from '../../components/common/StatusBadge'
import SkeletonLoader from '../../components/common/SkeletonLoader'
import {
  Search,
  Plus,
  Eye,
  Pencil,
  ToggleLeft,
  ToggleRight,
  Users,
  Filter,
  Phone,
} from 'lucide-react'

export default function StaffDirectory() {
  const [staff, setStaff] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [toggling, setToggling] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    async function fetchStaff() {
      try {
        const data = await usersService.listStaff()
        setStaff(Array.isArray(data) ? data : data.staff || [])
      } catch {
        // Handle error silently
      } finally {
        setLoading(false)
      }
    }
    fetchStaff()
  }, [])

  const filtered = useMemo(() => {
    return staff.filter((s) => {
      const matchesSearch =
        !search ||
        s.full_name?.toLowerCase().includes(search.toLowerCase()) ||
        s.designation?.toLowerCase().includes(search.toLowerCase()) ||
        s.phone?.includes(search)
      const matchesStatus =
        statusFilter === 'all' || s.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [staff, search, statusFilter])

  async function handleToggleStatus(id) {
    setToggling(id)
    try {
      await usersService.toggleStaffStatus(id)
      setStaff((prev) =>
        prev.map((s) =>
          (s.id || s._id) === id
            ? { ...s, status: s.status === 'active' ? 'inactive' : 'active' }
            : s
        )
      )
    } catch {
      // Handle error
    } finally {
      setToggling(null)
    }
  }

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Staff Directory</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {staff.length} team member{staff.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button onClick={() => navigate('/admin/staff/create')} className="btn-primary">
          <Plus className="h-4 w-4" />
          Add Staff
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, designation, or phone..."
            className="input-field pl-10"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field pl-10 pr-8 appearance-none min-w-[140px]"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {loading ? (
        <SkeletonLoader variant="table-row" count={5} />
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <Users className="h-12 w-12 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-500">
            {search || statusFilter !== 'all' ? 'No staff match your filters' : 'No staff members yet'}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {!search && statusFilter === 'all' && 'Click "Add Staff" to get started'}
          </p>
        </div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block card !p-0 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Staff Member
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Designation
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Phone
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map((member) => {
                  const id = member.id || member._id
                  return (
                    <tr key={id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="h-9 w-9 rounded-full gradient-primary flex items-center justify-center text-white text-sm font-bold shrink-0">
                            {member.full_name?.charAt(0) || '?'}
                          </div>
                          <span className="text-sm font-semibold text-slate-700">{member.full_name}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-slate-600">{member.designation || '—'}</td>
                      <td className="px-5 py-3.5 text-sm text-slate-500 font-mono">{member.phone}</td>
                      <td className="px-5 py-3.5">
                        <StatusBadge status={member.status || 'active'} />
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => navigate(`/admin/staff/${id}`)}
                            className="p-2 rounded-lg text-slate-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                            title="View"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => navigate(`/admin/staff/${id}/edit`)}
                            className="p-2 rounded-lg text-slate-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleToggleStatus(id)}
                            disabled={toggling === id}
                            className="p-2 rounded-lg text-slate-400 hover:text-amber-600 hover:bg-amber-50 transition-colors disabled:opacity-50"
                            title="Toggle Status"
                          >
                            {member.status === 'active' ? (
                              <ToggleRight className="h-4 w-4" />
                            ) : (
                              <ToggleLeft className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-3">
            {filtered.map((member) => {
              const id = member.id || member._id
              return (
                <div key={id} className="card-hover">
                  <div className="flex items-start gap-3">
                    <div className="h-10 w-10 rounded-full gradient-primary flex items-center justify-center text-white text-sm font-bold shrink-0">
                      {member.full_name?.charAt(0) || '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-sm font-bold text-slate-800 truncate">
                          {member.full_name}
                        </h3>
                        <StatusBadge status={member.status || 'active'} />
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{member.designation || 'Team Member'}</p>
                      <div className="flex items-center gap-1 mt-1 text-xs text-slate-400">
                        <Phone className="h-3 w-3" />
                        {member.phone}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-1.5 mt-3 pt-3 border-t border-slate-100">
                    <button
                      onClick={() => navigate(`/admin/staff/${id}`)}
                      className="btn-ghost !px-3 !py-1.5 !text-xs"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      View
                    </button>
                    <button
                      onClick={() => navigate(`/admin/staff/${id}/edit`)}
                      className="btn-ghost !px-3 !py-1.5 !text-xs"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </button>
                    <button
                      onClick={() => handleToggleStatus(id)}
                      disabled={toggling === id}
                      className="btn-ghost !px-3 !py-1.5 !text-xs"
                    >
                      {member.status === 'active' ? (
                        <ToggleRight className="h-3.5 w-3.5" />
                      ) : (
                        <ToggleLeft className="h-3.5 w-3.5" />
                      )}
                      {member.status === 'active' ? 'Disable' : 'Enable'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
