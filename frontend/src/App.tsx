import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import TickerDetail from './pages/TickerDetail'
import Backtest from './pages/Backtest'

export default function App() {
  return (
    <div className='app'>
      <nav>
        <Link to='/'>Dashboard</Link>
        <Link to='/backtest'>Backtest</Link>
      </nav>
      <main>
        <Routes>
          <Route path='/' element={<Dashboard />} />
          <Route path='/ticker/:ticker' element={<TickerDetail />} />
          <Route path='/backtest' element={<Backtest />} />
        </Routes>
      </main>
    </div>
  )
}
