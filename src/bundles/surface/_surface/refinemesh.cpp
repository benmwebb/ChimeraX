/*
 * === UCSF ChimeraX Copyright ===
 * Copyright 2016 Regents of the University of California.
 * All rights reserved.  This software provided pursuant to a
 * license agreement containing restrictions on its disclosure,
 * duplication and use.  For details see:
 * http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
 * This notice must be embedded in or attached to all copies,
 * including partial copies, of the software or any revisions
 * or derivations thereof.
 * === UCSF ChimeraX Copyright ===
 */

// ----------------------------------------------------------------------------
// Modify a planar surface triangulation to create uniform size triangles
// suited vertex coloring.
//
// The surface border vertices are not moved and no new border vertices are
// added.  The triangle size is comparable to the length of the longest border
// edge.  The algorithm divides long edges, collapses short edges, and swaps
// edges for dual edges.
//
// This is intended to clean up a triangulation of a cap for a clipped 3-D
// surface generated by OpenGL gluTess*() routines.  The glu tesselation code
// generates slender triangles across the entire cap using a sweepline
// technique.  Coloring the vertices of that triangulation does not allow
// showing isotropic fine scale color variation across the cap.
//
// This is a modified version of refinemesh2.cpp to improve speed.
// It bins split points and does not allow two close split points.
// Also it does away with collapses, and eliminates interleaving swaps
// with splits.
//
#include <iostream>			// use std::cerr
#include <map>				// use std::map, std::pair
#include <math.h>			// use sqrt()
#include <set>				// use std::set
#include <stdlib.h>			// use exit()
#include <vector>			// use std::vector

#include <Python.h>			// Use PyObject
#include <arrays/pythonarray.h>		// use array_from_python()
#include <arrays/rcarray.h>		// use FArray, IArray

namespace Cap_Calculation {

// ----------------------------------------------------------------------------
//
typedef float Real;
typedef int Index;
typedef Real Vertex[3];
typedef Real Vector[3];		// used for triangle normals
typedef Index Vertex_Index;
typedef Index Triangle_Index;
typedef Index Triangle_Side;
typedef Vertex_Index Triangle[3];
typedef std::vector<Triangle_Side> Triangle_Side_List;
typedef std::set<Vertex_Index> Iset;
typedef std::pair<Vertex_Index,Vertex_Index> Edge;
typedef std::map<Edge,Triangle_Index> Edge_Map;

// ----------------------------------------------------------------------------
// The array3 class is a substitute for std::vector<float[3]> which is not
// legal because arrays are not copyable in C++.
//
template <class T> class array3
{
public:
  array3()
    { values = NULL; used = allocated = 0; deallocate = false; }
  array3(T *v, Index n)
    { values = v; used = allocated = n; deallocate = false; }
  ~array3()
    {
      if (deallocate)
	delete [] values;
      this->values = NULL;
    }
  T *operator[](Index i)
    { return values + 3*i; }
  const T *operator[](Index i) const
    { return values + 3*i; }
  Index size() const { return used; }
  void push_back(T *triple)
    {
      if (size() == allocated) reallocate();
      set(size(), triple);
      used += 1;
    }
  void reallocate()
    {
      Index na = (allocated == 0 ? 1 : 2*allocated);
      T *nv = new T[3*na];
      Index s3 = 3*size();
      for (Index k = 0 ; k < s3 ; ++k)
	nv[k] = values[k];
      if (deallocate)
	delete [] values;
      this->values = nv;
      this->allocated = na;
      this->deallocate = true;
    }
  void set(Index i, T *t)
    { T *tto = (*this)[i]; tto[0] = t[0]; tto[1] = t[1]; tto[2] = t[2]; }

  T *values;
  Index used, allocated;
  bool deallocate;
};

// ----------------------------------------------------------------------------
//
typedef array3<Real> Varray;
typedef array3<Index> Tarray;

// ----------------------------------------------------------------------------
//
class Triangle_Neighbors
{
public:
  Triangle_Neighbors(Index n)
  {
    this->used = n;
    this->allocated = n;
    this->nt = new Triangle_Side[3*n];
  }
  ~Triangle_Neighbors()
  {
    delete [] nt;
    nt = NULL;
  }
  Triangle_Side operator[](Triangle_Side ts) const
  {
    return nt[ts];
  }
  void extend(Index e)
  {
    if (used + e > allocated)
      {
	Index new_size = (2*allocated > used + e ? 2*allocated : used + e);
	resize(new_size);
      }
    this->used += e;
  }
  void resize(Index n)
  {
    Triangle_Side *new_nt = new Triangle_Side[3*n];
    Triangle_Side max_ts = 3 * (n < used ? n : used);
    for (Triangle_Side ts = 0 ; ts < max_ts ; ++ts)
      new_nt[ts] = nt[ts];
    delete [] this->nt;
    this->allocated = n;
    this->nt = new_nt;
  }
  void set_neighbors(Triangle_Side ts0, Triangle_Side ts1)
  {
    if (ts0 != -1)
      nt[ts0] = ts1;
    if (ts1 != -1)
      nt[ts1] = ts0;
  }
private:
  int used, allocated;
  Triangle_Side *nt; // Array mapping triangle side to adjoining triangle side.
};

// ----------------------------------------------------------------------------
//
class Ipoint
{
public:
  bool operator<(const Ipoint &p) const
  {
    return (i[0] < p.i[0] ||
	    (i[0] == p.i[0] && (i[1] < p.i[1] ||
				(i[1] == p.i[1] && i[2] < p.i[2]))));
  }
  Index i[3];
};

// ----------------------------------------------------------------------------
//
static void refine_mesh(Varray &varray, Tarray &tarray,
			float subdivision_factor);
static Real maximum_border_edge_length2(const Varray &varray,
					const Tarray &tarray,
					const Triangle_Neighbors &tn);
static void split_long_edges(Varray &varray, Tarray &tarray,
			     Triangle_Neighbors &tn, Real elength2);
static void split_edge(Triangle_Side ts, Varray &varray, Tarray &tarray,
		       Triangle_Neighbors &tn, Triangle_Side_List &new_edges);
/*
static void collapse_short_edges(Varray &varray, Tarray &tarray,
				 Triangle_Neighbors &tn, Real elength2);
static bool collapse_edge(Triangle_Side ts, Varray &varray, Tarray &tarray,
			  Triangle_Neighbors &tn, Iset &moved_edges);
*/
static void swap_edges(Varray &varray, Tarray &tarray, Triangle_Neighbors &tn);
static bool swap_edge(Triangle_Side ts, Varray &varray, Tarray &tarray,
		      Triangle_Neighbors &em, Triangle_Side_List *check_again);
static void rearrange_edges(Varray &varray, Tarray &tarray,
			    Triangle_Neighbors &tn, Real min_aspect);
/*
static bool is_triangle_inverted(const Triangle tri, int corner,
				 const Varray &varray, const Vertex vnew);
*/
static void remove_unused_triangles_and_vertices(Varray &varray,
						 Tarray &tarray);
static void calculate_triangle_neighbors(const Tarray &tarray,
					 Triangle_Neighbors &tn);
static void calculate_edge_map(const Tarray &tarray, Edge_Map &em);
// static void check_triangle_neighbors(const Tarray &tarray, const Triangle_Neighbors &tn);
static void internal_edges(const Triangle_Neighbors &tn, const Tarray &tarray,
			   Triangle_Side_List &tslist);
/*
static bool vertex_edges(Triangle_Side ts, const Triangle_Neighbors &tn,
			 Triangle_Side_List &tslist);
*/
static bool is_unused_triangle(const Triangle_Index *tri);
static Triangle_Index triangle(Triangle_Side ts);
static int side(Triangle_Side ts);
static Triangle_Side triangle_side(Triangle_Index t, int side);
static void edge_vertex_indexes(Triangle_Side ts, const Tarray &tarray,
				Vertex_Index *i0, Vertex_Index *i1);
// static Vertex_Index vertex_index_1(Triangle_Side ts, const Tarray &tarray);
static Vertex_Index third_vertex_index(Triangle_Side ts, const Tarray &tarray);
static Triangle_Side next_side(Triangle_Side ts);
static Triangle_Side previous_side(Triangle_Side ts);
static Real side_length2(Triangle_Side ts, const Varray &varray,
			 const Tarray &tarray);
static Real triangle_area(const Triangle tri, const Varray &varray);
static Real triangle_area(const Vertex v0, const Vertex v1, const Vertex v2);
static void longest_triangle_side(const Triangle tri, const Varray &varray,
				  int *side, Real *elen2);
static Real longest_edge2(const Vertex v0, const Vertex v1, const Vertex v2);
static Real triangle_aspect(const Vertex v0, const Vertex v1, const Vertex v2);
static void triangle_normal(const Vertex v0, const Vertex v1, const Vertex v2,
			    Vector n);
static void midpoint(const Vertex u, const Vertex v, Vertex mid);
static void subtract(const Vector u, const Vector v, Vector diff);
static Real inner_product(const Vector u, const Vector v);
static void cross_product(const Vector u, const Vector v, Vector uv);
static Real length(const Vector v);
static Real distance2(const Vertex u, const Vertex v);
static Real rmin(Real a, Real b);

// ----------------------------------------------------------------------------
//
void refine_mesh(Real *vertices, Index n3, Index *triangles, Index m3,
		 float subdivision_factor,
		 Real **rvertices, Index *rn3, Index **rtriangles, Index *rm3)
{
  
  Varray varray(vertices, n3);
  varray.reallocate();		// Prevents modifying input data.
  Tarray tarray(triangles, m3);
  tarray.reallocate();		// Prevents modifying input data.
  refine_mesh(varray, tarray, subdivision_factor);
  
  varray.deallocate = false;	// Caller responsible for deallocating array
  *rvertices = varray.values;
  *rn3 = varray.size();
  
  tarray.deallocate = false;	// Caller responsible for deallocating array
  *rtriangles = tarray.values;
  *rm3 = tarray.size();
}

// ----------------------------------------------------------------------------
//
static void refine_mesh(Varray &varray, Tarray &tarray,
			float subdivision_factor)
{
  if (tarray.size() == 0)
    return;

  //  std::cerr << "making triangle neighbor array\n";
  Triangle_Neighbors tn(tarray.size());
  calculate_triangle_neighbors(tarray, tn);
  //  check_triangle_neighbors(tarray, tn);

  // The scale factor makes the mesh size match clipped isosurface mesh size.
  Real melength2 = maximum_border_edge_length2(varray, tarray, tn);
  //  std::cerr << "max edge length = " << sqrt(melength2) << std::endl;
  Real elength2 = 1.5 * melength2 / (subdivision_factor * subdivision_factor);

  //  std::cerr << "split long edges\n";
  // Splitting copies the vertex array and triangle list because they
  // need to be extended.
  split_long_edges(varray, tarray, tn, elength2);

  //  check_triangle_neighbors(tarray, tn);

  //  for (int i = 0 ; i < 2 ; ++i)
    {
      //      std::cerr << "collapse short edges\n";
      //      collapse_short_edges(varray, tarray, tn, elength2/9.0);
      //      std::cerr << "swap edges\n";
      swap_edges(varray, tarray, tn);
      //      check_triangle_neighbors(tarray, tn);
    }

  // Eliminate small aspect triangles, except for those caused by close
  // (unmovable) boundary points.
  Real min_aspect = .2;
  //  std::cerr << "rearrange edges\n";
  rearrange_edges(varray, tarray, tn, min_aspect);

  // The following renumbering invalidates the edge map.
  //  std::cerr << "remove unused\n";
  remove_unused_triangles_and_vertices(varray, tarray);
  //  std::cerr << std::endl;
}
    
// ----------------------------------------------------------------------------
//
static Real maximum_border_edge_length2(const Varray &varray,
					const Tarray &tarray,
					const Triangle_Neighbors &tn)
{
  Real mx = 0;
  Triangle_Index n = tarray.size();
  for (Triangle_Index t = 0 ; t < n ; ++t)
    if (!is_unused_triangle(tarray[t]))
      for (int s = 0 ; s < 3 ; ++s)
	{
	  Triangle_Side ts = triangle_side(t,s);
	  if (tn[ts] == -1)
	    {
	      Real d2 = side_length2(ts, varray, tarray);
	      if (d2 > mx)
		mx = d2;
	    }
	}
  return mx;
}

// ----------------------------------------------------------------------------
// Split all non-boundary edges until there lengths are reduced below elength.
// Distance elength must be greater than 2/3 the maximum border edge length
// or an infinite halfing loop can occur.
//
static void split_long_edges(Varray &varray, Tarray &tarray,
			     Triangle_Neighbors &tn, Real elength2)
{
  std::set<Ipoint> split_points;
  Real bin_size = .7*sqrt(elength2);
  Triangle_Side_List edges_to_check;
  internal_edges(tn, tarray, edges_to_check);
  int sc = 0;
  while (edges_to_check.size() > 0)
    {
      Triangle_Side_List new_edges;
      Index n = edges_to_check.size();
      for (Index i = 0 ; i < n ; ++i)
	{
	  Triangle_Side ts = edges_to_check[i];
	  Real elen2 = side_length2(ts, varray, tarray);
	  if (elen2 > elength2)
	    {
	      Vertex vmid;
	      Vertex_Index i0, i1;
	      edge_vertex_indexes(ts, tarray, &i0, &i1);
	      midpoint(varray[i0], varray[i1], vmid);
	      Ipoint bin;
	      for (int a = 0 ; a < 3 ; ++a)
		bin.i[a] = static_cast<Index>(vmid[a] / bin_size);
	      if (split_points.find(bin) == split_points.end())
		{
		  split_points.insert(bin);
		  split_edge(ts, varray, tarray, tn, new_edges);
		  sc += 1;
		}
	    }
	}
      edges_to_check = new_edges;
      //      std::cerr << "new round of edge splits\n";
    }
  //  std::cerr << sc << " splits ";
}

// ----------------------------------------------------------------------------
//
static void split_edge(Triangle_Side ts, Varray &varray, Tarray &tarray,
		       Triangle_Neighbors &tn, Triangle_Side_List &new_edges)
{
  // Add mid-point vertex
  Vertex_Index i0, i1;
  edge_vertex_indexes(ts, tarray, &i0, &i1);
  Vertex vmid;
  midpoint(varray[i0], varray[i1], vmid);
  Vertex_Index i = varray.size();
  varray.push_back(vmid);

  // Add two new triangles, and modify two existing triangles.
  Triangle_Index t0 = triangle(ts);
  Vertex_Index i2_t0 = third_vertex_index(ts, tarray);
  int i1_t0_index = side(next_side(ts));
  tarray[t0][i1_t0_index] = i;  
  Triangle_Index tinew0 = tarray.size();
  Triangle tnew0 = {i,i1,i2_t0};
  tarray.push_back(tnew0);

  Triangle_Side ts1 = tn[ts];
  Triangle_Index t1 = triangle(ts1);
  Vertex_Index i2_t1 = third_vertex_index(ts1, tarray);
  int i1_t1_index = side(ts1);
  tarray[t1][i1_t1_index] = i;
  Triangle_Index tinew1 = tarray.size();
  Triangle tnew1 = {i1,i,i2_t1};
  tarray.push_back(tnew1);

  // Update triangle neighbors
  tn.extend(2);
  tn.set_neighbors(triangle_side(tinew0,0), triangle_side(tinew1,0));
  tn.set_neighbors(triangle_side(tinew0,1), tn[next_side(ts)]);
  tn.set_neighbors(triangle_side(tinew0,2), next_side(ts));
  tn.set_neighbors(triangle_side(tinew1,2), tn[previous_side(ts1)]);
  tn.set_neighbors(triangle_side(tinew1,1), previous_side(ts1));

  //  std::cerr << "split " << i0 << " " << i1 << std::endl;
  //  check_triangle_neighbors(tarray, tn);

  new_edges.push_back(ts);
  new_edges.push_back(triangle_side(tinew0,0));
  new_edges.push_back(next_side(ts));
  new_edges.push_back(previous_side(ts1));
}

// ----------------------------------------------------------------------------
// Modifies input arrays.
//
/* Unused
static void collapse_short_edges(Varray &varray, Tarray &tarray,
				 Triangle_Neighbors &tn, Real elength2)
{
  Triangle_Side_List edges_to_check;
  internal_edges(tn, tarray, edges_to_check);
  int cc = 0;
  while (edges_to_check.size() > 0)
    {
      Iset moved_edges;
      Triangle_Side n = edges_to_check.size();
      for (Index i = 0 ; i < n ; ++i)
	{
	  Triangle_Side ts = edges_to_check[i];
	  if (is_unused_triangle(tarray[triangle(ts)]))
	    continue;
	  Real elen2 = side_length2(ts, varray, tarray);
	  if (elen2 < elength2)
	    if (collapse_edge(ts, varray, tarray, tn, moved_edges))
	      cc += 1;
	}
      edges_to_check.clear();
      for (Iset::iterator ei = moved_edges.begin() ; ei != moved_edges.end() ;
	   ++ei)
	edges_to_check.push_back(*ei);
    }
  //  std::cerr << cc << " collapses ";
}

// ----------------------------------------------------------------------------
//
static bool collapse_edge(Triangle_Side ts, Varray &varray, Tarray &tarray,
			  Triangle_Neighbors &tn, Iset &moved_edges)
{
  //  std::cerr << "collapse edge " << ts;
  // Don't collapse if either vertex is on surface border.
  Triangle_Side_List tslist0;
  bool on_edge = vertex_edges(ts, tn, tslist0);
  if (on_edge)
    return false;

  Triangle_Side ts1 = tn[ts];
  Triangle_Side_List tslist1;
  on_edge = vertex_edges(ts1, tn, tslist1);
  if (on_edge)
    return false;

  //  std::cerr << " not on border";
  //  std::cerr << "checking collapse neighbors\n";
  // Collapsing can generate degenerate graph such as
  // having two triangles joined along two different edges, if the
  // vertices around i0 and i1 are not unique.  Check for this.

  // TODO: Could replace stl::set with marker array as optimization.
  Iset vt;
  Vertex_Index i0, i1;
  edge_vertex_indexes(ts, tarray, &i0, &i1);
  vt.insert(i0);
  vt.insert(i1);
  for (Triangle_Side_List::iterator tsi = tslist0.begin() + 1 ;
       tsi != tslist0.end() ; ++tsi)
    {
      Vertex_Index i = vertex_index_1(*tsi, tarray);
      if (vt.find(i) != vt.end())
	return false;        // Vertex used twice around i0, i1.
      vt.insert(i);
    }
  for (Triangle_Side_List::iterator tsi = tslist1.begin() + 1 ;
       tsi != tslist1.end() ; ++tsi)
    {
      Vertex_Index i = vertex_index_1(*tsi, tarray);
      if (vt.find(i) != vt.end())
	return false;        // Vertex used twice around i0, i1.
      vt.insert(i);
    }
  
  //  std::cerr << " no vertex reuse ";
  // Compute edge mid-point.  Reuse index i0 for the collapsed vertex.
  Vertex vmid;
  midpoint(varray[i0], varray[i1], vmid);

  //  std::cerr << "checking collapse inversion\n";
  // Check that collapse does not invert any triangle.
  for (Triangle_Side_List::iterator tsi = tslist0.begin() ;
       tsi+1 != tslist0.end() ; ++tsi)
    if (is_triangle_inverted(tarray[triangle(*tsi)], side(*tsi), varray, vmid))
      return false;
  for (Triangle_Side_List::iterator tsi = tslist1.begin() ;
       tsi+1 != tslist1.end() ; ++tsi)
    if (is_triangle_inverted(tarray[triangle(*tsi)], side(*tsi), varray, vmid))
      return false;

  //  std::cerr << " no inversion ";
  varray.set(i0, vmid);

  tn.set_neighbors(tn[next_side(ts)], tn[previous_side(ts)]);
  tn.set_neighbors(tn[next_side(ts1)], tn[previous_side(ts1)]);

  // Make all triangles use new mid-point.
  for (Triangle_Side_List::iterator tsi = tslist1.begin() ;
       tsi+1 != tslist1.end() ; ++tsi)
    tarray[triangle(*tsi)][side(*tsi)] = i0;
    
  // Mark two collapsed triangles as removed.
  tarray[triangle(ts)][0] = -1;
  tarray[triangle(ts1)][0] = -1;

  //  std::cerr << "update moved edges, collapse\n";
  for (Triangle_Side_List::iterator tsi = tslist0.begin() ;
       tsi+1 != tslist0.end() ; ++tsi)
    moved_edges.insert(*tsi);
  for (Triangle_Side_List::iterator tsi = tslist1.begin() ;
       tsi+1 != tslist1.end() ; ++tsi)
    moved_edges.insert(*tsi);

  return true;
}
*/

// ----------------------------------------------------------------------------
// Remove an edge and add the edge joining the opposing corners if the new
// edge would be shorter.
//
static void swap_edges(Varray &varray, Tarray &tarray, Triangle_Neighbors &tn)
{
  Triangle_Side_List edges_to_check;
  internal_edges(tn, tarray, edges_to_check);
  int sc = 0;
  while (edges_to_check.size() > 0)
    {
      Triangle_Side_List check_again;
      Triangle_Side n = edges_to_check.size();
      for (Index i = 0 ; i < n ; ++i)
	{
	  Triangle_Side ts = edges_to_check[i];
	  Triangle_Side ts1 = tn[ts];
	  if (ts1 == -1 ||
	      is_unused_triangle(tarray[triangle(ts)]) ||
	      is_unused_triangle(tarray[triangle(ts1)]))
	    continue;
	  Real elen2 = side_length2(ts, varray, tarray);
	  Vertex_Index c0 = third_vertex_index(ts, tarray);
	  Vertex_Index c1 = third_vertex_index(ts1, tarray);
	  Real clen2 = distance2(varray[c1], varray[c0]);
	  if (clen2 < elen2)
	    if (swap_edge(ts, varray, tarray, tn, &check_again))
	      sc += 1;
	}
      edges_to_check = check_again;
    }
  //  std::cerr << sc << " swaps ";
}

// ----------------------------------------------------------------------------
//
static bool swap_edge(Triangle_Side ts, Varray &varray, Tarray &tarray,
		      Triangle_Neighbors &tn, Triangle_Side_List *check_again)
{
  Triangle_Index t0 = triangle(ts);
  Vertex_Index i0, i1;
  edge_vertex_indexes(ts, tarray, &i0, &i1);
  Vertex_Index i2_t0 = third_vertex_index(ts, tarray);

  Triangle_Side ts1 = tn[ts];
  Triangle_Index t1 = triangle(ts1);
  Vertex_Index i2_t1 = third_vertex_index(ts1, tarray);

  Triangle_Side ts2 = tn[next_side(ts)], ts3 = tn[next_side(ts1)];
  if ((ts2 != -1 && third_vertex_index(ts2, tarray) == i2_t1) ||
      (ts3 != -1 && third_vertex_index(ts3, tarray) == i2_t0))
    return false;		// Swapped edge already exists

  // Remove edge (i0,i1) and add edge (i2_t0,i2_t1).
  Real *v0 = varray[i0];
  Real *v1 = varray[i1];
  Real *v2 = varray[i2_t0];
  Real *v3 = varray[i2_t1];

  // Don't allow minimum triangle aspect ratio to get smaller.
  if (rmin(triangle_aspect(v0,v2,v3), triangle_aspect(v1,v2,v3)) <
      rmin(triangle_aspect(v0,v1,v2), triangle_aspect(v0,v1,v3)))
    return false;

  // Check if new edge stays within triangles on either side of (i0,i1)
  Vector n1, n2;
  triangle_normal(v0,v2,v3,n1);
  triangle_normal(v1,v2,v3,n2);
  if (inner_product(n1, n2) > 0)
    return false; // New edge would go outside two triangles
    
  // Change triangles
  Triangle tswap0 = {i0,i2_t1,i2_t0};
  tarray.set(t0, tswap0);
  Triangle tswap1 = {i1,i2_t0,i2_t1};
  tarray.set(t1, tswap1);

  // Update triangle neighbors
  // Need to compute surrounding triangles before setting.
  Triangle_Side tn0 = tn[next_side(ts)], tp0 = tn[previous_side(ts)];
  Triangle_Side tn1 = tn[next_side(ts1)], tp1 = tn[previous_side(ts1)];
  tn.set_neighbors(tn0, triangle_side(t1,0));
  tn.set_neighbors(tp0, triangle_side(t0,2));
  tn.set_neighbors(tn1, triangle_side(t0,0));
  tn.set_neighbors(tp1, triangle_side(t1,2));
  tn.set_neighbors(triangle_side(t0,1), triangle_side(t1,1));

  //  std::cerr << "swapped edge " << i0 << " " << i1 << std::endl;
  //  check_triangle_neighbors(tarray, tn);

  if (check_again)
    {
      check_again->push_back(triangle_side(t0,0));
      check_again->push_back(triangle_side(t0,2));
      check_again->push_back(triangle_side(t1,0));
      check_again->push_back(triangle_side(t1,2));
    }

  return true;
}

// ----------------------------------------------------------------------------
// Rearrange edges to eliminate slender triangles.
// Unused.  Not sure why I didn't originally just swap edges whenever the
// new edge is shorter as in the swap_edges() routine.
//
// The swap_edges() routine won't eliminate some triangles with tiny aspect
// ratio where the swapped edge would be longer.
//
static void rearrange_edges(Varray &varray, Tarray &tarray,
			    Triangle_Neighbors &tn, Real min_aspect)
{
  Triangle_Index n = tarray.size();
  for (Triangle_Index t = 0 ; t < n ; ++t)
    {
      Triangle_Index *tri = tarray[t];
      if (is_unused_triangle(tri))
	continue;            // unused triangle
      int s;
      Real elen2;
      longest_triangle_side(tri, varray, &s, &elen2);
      Triangle_Side ts = triangle_side(t,s);
      if (tn[ts] != -1)
	{
	  Real area = triangle_area(tri, varray);
	  Real aspect = 2 * area / elen2;
	  if (aspect < min_aspect)
	    swap_edge(ts, varray, tarray, tn, NULL);
	}
    }
}
// ----------------------------------------------------------------------------
//
/* Unused
static bool is_triangle_inverted(const Triangle tri, int corner,
				 const Varray &varray, const Vertex vnew)
{
  Vertex_Index i0 = tri[corner];
  const Real *v0 = varray[i0];
  Vertex_Index i1 = tri[(corner+1)%3];
  const Real *v1 = varray[i1];
  Vertex_Index i2 = tri[(corner+2)%3];
  const Real *v2 = varray[i2];
  Vector n, nnew;
  triangle_normal(v0, v1, v2, n);
  triangle_normal(vnew, v1, v2, nnew);
  bool inverted = (inner_product(n, nnew) < 0);
  return inverted;
}
*/

// ----------------------------------------------------------------------------
// Unused triangles are marked with vertex index -1 in first position.
//
static void remove_unused_triangles_and_vertices(Varray &varray,
						 Tarray &tarray)
{
  // Remove unused triangles.
  Triangle_Index j = 0;
  Triangle_Index m = tarray.size();
  for (Triangle_Index k = 0 ; k < m ; ++k)
    {
      if (is_unused_triangle(tarray[k]))
	continue;
      if (j < k)
	tarray.set(j, tarray[k]);
      j += 1;
    }
  tarray.used = j;
  m = tarray.size();

  // Remove unused vertices.
  Vertex_Index n = varray.size();
  Vertex_Index *used = new int[n];
  Vertex_Index *vnew = used;
  for (Triangle_Index k = 0 ; k < m ; ++k)
    {
      Triangle_Index *tri = tarray[k];
      used[tri[0]] = 1;
      used[tri[1]] = 1;
      used[tri[2]] = 1;
    }
  Vertex_Index l = 0;
  for (Vertex_Index k = 0 ; k < n ; ++k)
    {
      if (used[k])
	{
	  varray.set(l, varray[k]);
	  vnew[k] = l;
	  l += 1;
	}
      else
	vnew[k] = -1;
    }
  varray.used = l;

  // Fix triangle vertex indices to use new numbering
  for (Triangle_Index k = 0 ; k < m ; ++k)
    {
      Triangle_Index *tri = tarray[k];
      for (int a = 0 ; a < 3 ; ++a)
	tri[a] = vnew[tri[a]];
    }

  delete [] used;
}

// ----------------------------------------------------------------------------
// Edge map takes an ordered pair of vertex indices as key and has value equal
// to the index of the triangle having that edge, traversed in the given order.
//
static void calculate_triangle_neighbors(const Tarray &tarray,
					 Triangle_Neighbors &tn)
{
  Edge_Map em;
  calculate_edge_map(tarray, em);

  Triangle_Index n = tarray.size();
  for (Triangle_Index t = 0 ; t < n ; ++t)
    {
      const Triangle_Index *tri = tarray[t];
      if (is_unused_triangle(tri))
	continue;
      Edge erev;
      for (int s = 0 ; s < 3 ; ++s)
	{
	  Triangle_Side ts = triangle_side(t,s);
	  edge_vertex_indexes(ts, tarray, &erev.second, &erev.first);
	  Edge_Map::iterator ei = em.find(erev);
	  Triangle_Side ts1 = (ei == em.end() ? -1 : em[erev]);
	  tn.set_neighbors(ts, ts1);
	}
    }
}

// ----------------------------------------------------------------------------
// Edge map takes an ordered pair of vertex indices as key and has value equal
// to the Triangle_Side for that edge, traversed in the given order.
//
static void calculate_edge_map(const Tarray &tarray, Edge_Map &em)
{
  em.clear();

  Triangle_Index n = tarray.size();
  for (Triangle_Index t = 0 ; t < n ; ++t)
    {
      const Triangle_Index *tri = tarray[t];
      if (is_unused_triangle(tri))
	continue;
      for (int s = 0 ; s < 3 ; ++s)
	{
	  Edge e(tri[s], tri[(s+1)%3]);
	  if (em.find(e) == em.end())
	    em[e] = triangle_side(t,s);
	  else
	    {
	      Triangle_Side tsp = em.find(e)->second;
	      const Triangle_Index *trip = tarray[triangle(tsp)];
	      std::cerr << "Error in refinemesh.cpp calculate_edge_map(): "
			<< "Two triangles (" << triangle(tsp) << "." << side(tsp) << " "
			<< trip[0] << " " << trip[1] << " " << trip[2]
			<< " and " << t << "." << s << " "
			<< tri[0] << " " << tri[1] << " " << tri[2]
			<< ") traverse edge ("
			<< e.first << " - " << e.second
			<< ") in same direction.\n";
	      exit(1);
	    }
	}
    }
}

// ----------------------------------------------------------------------------
//
/* Unused
static void check_triangle_neighbors(const Tarray &tarray,
				     const Triangle_Neighbors &tn)
{
  Triangle_Neighbors tn2(tarray.size());
  calculate_triangle_neighbors(tarray, tn2);
  Triangle_Index n = tarray.size();
  for (Triangle_Index t = 0 ; t < n ; ++t)
    if (!is_unused_triangle(tarray[t]))
      for (int s = 0 ; s < 3 ; ++s)
	{
	  Triangle_Side ts = triangle_side(t,s);
	  if (tn[ts] != tn2[ts])
	    std::cerr << "Triangle " << t << " side " << s
		      << " neighbor " << tn[ts]
		      << " should be " << tn2[ts] << std::endl;
	}
}
*/

// ----------------------------------------------------------------------------
//
static void internal_edges(const Triangle_Neighbors &tn, const Tarray &tarray,
			   Triangle_Side_List &tslist)
{
  Triangle_Index n = tarray.size();
  for (Triangle_Index t = 0 ; t < n ; ++t)
    if (!is_unused_triangle(tarray[t]))
      for (int s = 0 ; s < 3 ; ++s)
	{
	  Triangle_Side ts = triangle_side(t,s);
	  Vertex_Index i0, i1;
	  edge_vertex_indexes(ts, tarray, &i0, &i1);
	  if (i0 < i1)
	    if (tn[ts] != -1)
	      tslist.push_back(ts);
	}
}
    
// ----------------------------------------------------------------------------
// Return list of triangle sides about a vertex by traversing in a circle
// around the vertex.  The given triangle side is not included in the list.
// If the vertex is on the border then true is returned, and not all triangle
// sides will be found.  Otherwise, true is returned.
//
/* Unused
static bool vertex_edges(Triangle_Side ts,
			 const Triangle_Neighbors &tn,
			 Triangle_Side_List &tslist)
{
  Triangle_Side ts_next;
  for (Triangle_Side ts_cur = ts ;
       (ts_next = tn[previous_side(ts_cur)], ts_next != ts && ts_next != -1) ;
       ts_cur = ts_next)
    tslist.push_back(ts_next);

  return ts_next == -1;
}
*/

// ----------------------------------------------------------------------------
//
inline static bool is_unused_triangle(const Triangle_Index *tri)
  { return tri[0] == -1; }

// ----------------------------------------------------------------------------
//
inline static Triangle_Index triangle(Triangle_Side ts)
  { return ts / 3; }
inline static int side(Triangle_Side ts)
  { return ts % 3; }
inline static Triangle_Side triangle_side(Triangle_Index t, int side)
  { return 3*t + side; }

// ----------------------------------------------------------------------------
//
inline static void edge_vertex_indexes(Triangle_Side ts, const Tarray &tarray, Vertex_Index *i0, Vertex_Index *i1)
{
  const Triangle_Index *tri = tarray[triangle(ts)];
  int s = side(ts);
  *i0 = tri[s];
  *i1 = tri[(s+1)%3];
}
//inline static Vertex_Index vertex_index_1(Triangle_Side ts, const Tarray &tarray)
//  { return tarray[triangle(ts)][(side(ts)+1)%3]; }
inline static Vertex_Index third_vertex_index(Triangle_Side ts, const Tarray &tarray)
  { return tarray[triangle(ts)][(side(ts)+2)%3]; }
inline static Triangle_Side next_side(Triangle_Side ts)
  { return triangle_side(triangle(ts), (side(ts)+1) % 3); }
inline static Triangle_Side previous_side(Triangle_Side ts)
  { return triangle_side(triangle(ts), (side(ts)+2) % 3); }

// ----------------------------------------------------------------------------
//
static Real side_length2(Triangle_Side ts, const Varray &varray,
			 const Tarray &tarray)
{
  Vertex_Index i0, i1;
  edge_vertex_indexes(ts, tarray, &i0, &i1);
  Real d2 = distance2(varray[i0], varray[i1]);
  return d2;
}

// ----------------------------------------------------------------------------
//
static Real triangle_area(const Triangle tri, const Varray &varray)
{
  return triangle_area(varray[tri[0]], varray[tri[1]], varray[tri[2]]);
}

// ----------------------------------------------------------------------------
//
static Real triangle_area(const Vertex v0, const Vertex v1, const Vertex v2)
{
  Vector n;
  triangle_normal(v0, v1, v2, n);
  Real area = .5 * length(n);
  return area;
}

// ----------------------------------------------------------------------------
//
static void longest_triangle_side(const Triangle tri, const Varray &varray,
				  int *side, Real *elen2)
{
  Vertex_Index i0 = tri[0], i1 = tri[1], i2 = tri[2];
  const Real *v0 = varray[i0], *v1 = varray[i1], *v2 = varray[i2];
  Real d0 = distance2(v0,v1), d1 = distance2(v1,v2), d2 = distance2(v2,v0);
  if (d0 > d1)
    if (d0 > d2) { *side = 0; *elen2 = d0; }
    else         { *side = 1; *elen2 = d2; }
  else
    if (d1 > d2) { *side = 1; *elen2 = d1; }
    else         { *side = 2; *elen2 = d2; }
}

// ----------------------------------------------------------------------------
//
static Real longest_edge2(const Vertex v0, const Vertex v1, const Vertex v2)
{
  Real d0 = distance2(v0,v1), d1 = distance2(v1,v2), d2 = distance2(v2,v0);
  Real dmax = (d0 > d1 ? (d2 > d0 ? d2 : d0) : (d2 > d1 ? d2 : d1));
  return dmax;
}

// ----------------------------------------------------------------------------
//
static Real triangle_aspect(const Vertex v0, const Vertex v1, const Vertex v2)
{
  Real area = triangle_area(v0, v1, v2);
  Real max_edge2 = longest_edge2(v0, v1, v2);
  Real aspect = 2 * area / max_edge2;
  return aspect;
}

// ----------------------------------------------------------------------------
//
static void triangle_normal(const Vertex v0, const Vertex v1, const Vertex v2,
			    Vector n)
{
  Vector v10, v20;
  subtract(v1, v0, v10);
  subtract(v2, v0, v20);
  cross_product(v10, v20, n);
}

// ----------------------------------------------------------------------------
//
static void midpoint(const Vertex u, const Vertex v, Vertex mid)
{
  for (int a = 0 ; a < 3 ; ++a)
    mid[a] = .5 * (u[a] + v[a]);
}

// ----------------------------------------------------------------------------
//
static void subtract(const Vector u, const Vector v, Vector diff)
{
  for (int a = 0 ; a < 3 ; ++a)
    diff[a] = u[a] - v[a];
}

// ----------------------------------------------------------------------------
//
static Real inner_product(const Vector u, const Vector v)
{
  return u[0]*v[0] + u[1]*v[1] + u[2]*v[2];
}

// ----------------------------------------------------------------------------
//
static void cross_product(const Vector u, const Vector v, Vector uv)
{
  uv[0] = u[1]*v[2]-u[2]*v[1];
  uv[1] = -u[0]*v[2]+u[2]*v[0];
  uv[2] = u[0]*v[1]-u[1]*v[0];
}

// ----------------------------------------------------------------------------
//
static Real length(const Vector v)
{
  double d = sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
  return static_cast<Real>(d);
}

// ----------------------------------------------------------------------------
//
static Real distance2(const Vertex u, const Vertex v)
{
  Real x = u[0]-v[0], y = u[1]-v[1], z = u[2]-v[2];
  return x*x + y*y + z*z;
}

// ----------------------------------------------------------------------------
//
static Real rmin(Real a, Real b)
{
  return (a < b ? a : b);
}

} // end of namespace Cap_Calculation

// ----------------------------------------------------------------------------
//
extern "C" PyObject *refine_mesh(PyObject *, PyObject *args)
{
  FArray varray;
  IArray tarray;
  float subdivision_factor;
  if (!PyArg_ParseTuple(args, const_cast<char *>("O&Of"),
			&parse_float_n3_array, &varray,
			&parse_int_n3_array, &tarray,
			&subdivision_factor))
    return NULL;

  FArray vcontig = varray.contiguous_array();
  float *vvalues = vcontig.values();
  int vsize = varray.size(0);

  IArray tcontig = tarray.contiguous_array();
  int *tvalues = tcontig.values();
  int tsize = tarray.size(0);

  Cap_Calculation::Index rvsize, *rt, rtsize;
  Cap_Calculation::Real *rv;

  Cap_Calculation::refine_mesh(vvalues, vsize, tvalues, tsize,
			       subdivision_factor,
			       &rv, &rvsize, &rt, &rtsize);

  PyObject *rvarray = c_array_to_python(rv, rvsize, 3);
  PyObject *rtarray = c_array_to_python(rt, rtsize, 3);

  PyObject *geom = PyTuple_New(2);
  PyTuple_SetItem(geom, 0, rvarray);
  PyTuple_SetItem(geom, 1, rtarray);

  return geom;
}