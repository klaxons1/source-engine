#pragma once
// Only allocator adapter for the host test. The production math/COM implementation
// is compiled unchanged; Android uses the real engine CUtlVector allocator.
#include <vector>
template<class T> class CUtlVector {
  std::vector<T> values;
public:
  int Count() const { return int(values.size()); }
  void AddToTail() { values.emplace_back(); }
  void AddToTail(const T& t) { values.push_back(t); }
  void Remove(int i) { values.erase(values.begin()+i); }
  T& operator[](int i) { return values.at(i); }
};
