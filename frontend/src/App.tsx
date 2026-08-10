import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Homepage from './Homepage'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import NotFound from './pages/NotFound'

import CustomerLayout from './components/layout/CustomerLayout'
import CustomerOverview from './pages/customer/CustomerOverview'
import FindParking from './pages/customer/FindParking'
import MyBookings from './pages/customer/MyBookings'
import BookingDetail from './pages/customer/BookingDetail'
import Profile from './pages/customer/Profile'

import AdminLayout from './components/layout/AdminLayout'
import AdminOverview from './pages/admin/AdminOverview'
import AdminSlots from './pages/admin/AdminSlots'
import AdminBookings from './pages/admin/AdminBookings'
import AdminGates from './pages/admin/AdminGates'
import AdminCustomers from './pages/admin/AdminCustomers'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Homepage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route
            path="/customer"
            element={
              <ProtectedRoute allow="customer">
                <CustomerLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<CustomerOverview />} />
            <Route path="find" element={<FindParking />} />
            <Route path="bookings" element={<MyBookings />} />
            <Route path="bookings/:id" element={<BookingDetail />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route
            path="/admin"
            element={
              <ProtectedRoute allow="admin">
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AdminOverview />} />
            <Route path="slots" element={<AdminSlots />} />
            <Route path="bookings" element={<AdminBookings />} />
            <Route path="gates" element={<AdminGates />} />
            <Route path="customers" element={<AdminCustomers />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
