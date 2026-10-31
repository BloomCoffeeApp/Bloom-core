import { createContext, useContext } from 'react'

interface TourContextValue {
  start: () => void
}

export const TourContext = createContext<TourContextValue>({ start: () => {} })

export const useTour = () => useContext(TourContext)
