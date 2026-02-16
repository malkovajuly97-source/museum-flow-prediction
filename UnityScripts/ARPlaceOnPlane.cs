using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;

/// <summary>
/// По тапу/клику размещает AR Content на найденной AR-плоскости (стол, пол).
/// Нужны: AR Raycast Manager на этом же объекте и ссылка на AR Content.
/// </summary>
[RequireComponent(typeof(ARRaycastManager))]
public class ARPlaceOnPlane : MonoBehaviour
{
    [Header("Объект для размещения")]
    [Tooltip("Родитель пола и агентов — будет перемещён в точку тапа на плоскости.")]
    public Transform contentToPlace;

    [Header("Смещение")]
    [Tooltip("Высота над плоскостью (Y в локальных единицах), чтобы пол не уходил в стол.")]
    public float heightOffset = 0f;

    ARRaycastManager _raycastManager;
    static readonly List<ARRaycastHit> s_Hits = new List<ARRaycastHit>();

    void Awake()
    {
        _raycastManager = GetComponent<ARRaycastManager>();
    }

    void Update()
    {
        if (contentToPlace == null) return;

        Vector2 screenPoint = GetScreenPoint();
        if (screenPoint == default) return;

        if (_raycastManager.Raycast(screenPoint, s_Hits, TrackableType.PlaneWithinPolygon))
        {
            ARRaycastHit hit = s_Hits[0];
            Pose pose = hit.pose;
            contentToPlace.position = pose.position + Vector3.up * heightOffset;
            contentToPlace.rotation = pose.rotation;
        }
    }

    Vector2 GetScreenPoint()
    {
#if UNITY_EDITOR
        if (Input.GetMouseButtonDown(0))
            return Input.mousePosition;
#else
        if (Input.touchCount > 0 && Input.GetTouch(0).phase == TouchPhase.Began)
            return Input.GetTouch(0).position;
#endif
        return default;
    }
}
