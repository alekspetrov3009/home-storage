import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Boxes from "./pages/Boxes";
import BoxDetail from "./pages/BoxDetail";
import Items from "./pages/Items";
import ItemDetail from "./pages/ItemDetail";
import AddItem from "./pages/AddItem";
import Locations from "./pages/Locations";
import Trash from "./pages/Trash";
import Search from "./pages/Search";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="boxes" element={<Boxes />} />
        {/* Маршрут QR-кодов: именно /box с query ?box={id} */}
        <Route path="box" element={<BoxDetail />} />
        <Route path="items" element={<Items />} />
        <Route path="item/:id" element={<ItemDetail />} />
        <Route path="add" element={<AddItem />} />
        <Route path="locations" element={<Locations />} />
        <Route path="trash" element={<Trash />} />
        <Route path="search" element={<Search />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
